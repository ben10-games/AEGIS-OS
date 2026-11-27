// AEGIS App Center (v3, M12): find, install, update and remove applications from Flathub
// for the user's own account.
//
// Everything goes through Flatpak's own command-line tool with --user, so applications
// are installed into the user's home on the persistent disk and nothing ever asks for
// administrator rights. Flatpak checks the signatures of what it downloads (the Flathub
// remote's key from Fedora's fedora-flathub-remote). The catalogue is Flathub's AppStream
// data, which Flatpak keeps in the user installation.
//
// Wording rule (owner amendment 7): "Verified publisher" means Flathub confirmed who
// publishes an app. Nothing here makes a safety claim about an app; its permissions are
// shown instead.
//
// `aegis-appcenter --check-updates` (a daily user timer) only tells the user that updates
// are available. Updates are applied only when the user asks.
#include <algorithm>
#include <functional>

#include <QDBusConnection>
#include <QDBusMessage>
#include <QDir>
#include <QFile>
#include <QGuiApplication>
#include <QHash>
#include <QProcess>
#include <QQmlApplicationEngine>
#include <QQmlContext>
#include <QQuickStyle>
#include <QRegularExpression>
#include <QSet>
#include <QStandardPaths>
#include <QTimer>
#include <QXmlStreamReader>

struct App {
    QString id, name, summary, description, developer, license, icon;
    QStringList categories, screenshots;
    bool verified = false;
};

static QString appstreamDir()
{
    return QDir::homePath()
           + QStringLiteral("/.local/share/flatpak/appstream/flathub/x86_64/active");
}

// Plain-language meaning and weight of a Flatpak permission. "high" = can reach your
// files, devices or other programs broadly; "medium" = noticeable; "low" = routine.
static QVariantMap permission(const QString &text, const QString &level)
{
    return {{QStringLiteral("text"), text}, {QStringLiteral("level"), level}};
}

QVariantList permissionsFromMetadata(const QString &metadata)
{
    QVariantList list;
    QString group;
    QSet<QString> seen;
    auto add = [&](const QString &text, const QString &level) {
        if (!seen.contains(text)) {
            seen.insert(text);
            list << permission(text, level);
        }
    };
    for (const QString &raw : metadata.split(QLatin1Char('\n'))) {
        const QString line = raw.trimmed();
        if (line.startsWith(QLatin1Char('['))) {
            group = line;
            continue;
        }
        const int at = line.indexOf(QLatin1Char('='));
        if (at < 0)
            continue;
        const QString key = line.left(at);
        const QStringList values = line.mid(at + 1).split(QLatin1Char(';'), Qt::SkipEmptyParts);
        if (group == QLatin1String("[Context]")) {
            for (const QString &v : values) {
                if (key == QLatin1String("shared") && v == QLatin1String("network"))
                    add(QStringLiteral("Network and the internet"), QStringLiteral("medium"));
                else if (key == QLatin1String("sockets")) {
                    if (v == QLatin1String("x11"))
                        add(QStringLiteral("Older display system (X11): can see what you type in other X11 applications"), QStringLiteral("high"));
                    else if (v == QLatin1String("pulseaudio"))
                        add(QStringLiteral("Sound, and the microphone"), QStringLiteral("medium"));
                    else if (v == QLatin1String("system-bus") || v == QLatin1String("session-bus"))
                        add(QStringLiteral("Talk to all services of the system or your session"), QStringLiteral("high"));
                    else if (v == QLatin1String("ssh-auth"))
                        add(QStringLiteral("Use your SSH keys"), QStringLiteral("high"));
                    else if (v == QLatin1String("pcsc"))
                        add(QStringLiteral("Smart cards"), QStringLiteral("medium"));
                    else if (v == QLatin1String("cups"))
                        add(QStringLiteral("Printing"), QStringLiteral("low"));
                } else if (key == QLatin1String("devices")) {
                    if (v == QLatin1String("all"))
                        add(QStringLiteral("All devices: cameras, USB devices, game controllers"), QStringLiteral("high"));
                    else if (v == QLatin1String("dri"))
                        add(QStringLiteral("Graphics acceleration"), QStringLiteral("low"));
                    else if (v == QLatin1String("kvm"))
                        add(QStringLiteral("Run virtual machines"), QStringLiteral("medium"));
                } else if (key == QLatin1String("filesystems")) {
                    const QString path = v.section(QLatin1Char(':'), 0, 0);
                    const bool readOnly = v.endsWith(QLatin1String(":ro"));
                    const QString how = readOnly ? QStringLiteral(" (read only)") : QString();
                    if (path == QLatin1String("host") || path == QLatin1String("host-os")
                        || path == QLatin1String("host-etc"))
                        add(QStringLiteral("All files on this computer") + how, QStringLiteral("high"));
                    else if (path == QLatin1String("home") || path == QLatin1String("~"))
                        add(QStringLiteral("All files in your home folder") + how, QStringLiteral("high"));
                    else if (path.startsWith(QLatin1String("xdg-")))
                        add(QStringLiteral("Your %1 folder").arg(path.mid(4).replace(QLatin1Char('-'), QLatin1Char(' '))) + how,
                            QStringLiteral("medium"));
                    else
                        add(QStringLiteral("Files in %1").arg(path) + how, QStringLiteral("medium"));
                } else if (key == QLatin1String("features") && v == QLatin1String("devel")) {
                    add(QStringLiteral("Inspect other programs (debugging)"), QStringLiteral("high"));
                } else if (key == QLatin1String("features") && v == QLatin1String("bluetooth")) {
                    add(QStringLiteral("Bluetooth"), QStringLiteral("medium"));
                }
            }
        } else if (group == QLatin1String("[System Bus Policy]") && !key.isEmpty()) {
            add(QStringLiteral("Talk to system service %1").arg(key), QStringLiteral("medium"));
        }
    }
    if (list.isEmpty())
        list << permission(QStringLiteral("No special access: it runs in its sandbox only"), QStringLiteral("low"));
    return list;
}

class AppCenter : public QObject
{
    Q_OBJECT
    Q_PROPERTY(bool busy READ busy NOTIFY busyChanged)
    Q_PROPERTY(QString status READ status NOTIFY statusChanged)
    Q_PROPERTY(int progress READ progress NOTIFY progressChanged)
    Q_PROPERTY(QString error READ error NOTIFY errorChanged)
    Q_PROPERTY(int catalogueSize READ catalogueSize NOTIFY catalogueChanged)
    Q_PROPERTY(QStringList installedIds READ installedIds NOTIFY installedChanged)
    Q_PROPERTY(QStringList updateIds READ updateIds NOTIFY updatesChanged)

public:
    using QObject::QObject;

    bool busy() const { return m_job != nullptr; }
    QString status() const { return m_status; }
    int progress() const { return m_progress; }
    QString error() const { return m_error; }
    int catalogueSize() const { return int(m_apps.size()); }
    QStringList installedIds() const { return m_installed; }
    QStringList updateIds() const { return m_updates; }

    Q_INVOKABLE QVariantList categories() const
    {
        static const QList<QPair<QString, QString>> list = {
            {QStringLiteral("AudioVideo"), QStringLiteral("Audio and video")},
            {QStringLiteral("Development"), QStringLiteral("Development")},
            {QStringLiteral("Education"), QStringLiteral("Education")},
            {QStringLiteral("Game"), QStringLiteral("Games")},
            {QStringLiteral("Graphics"), QStringLiteral("Graphics")},
            {QStringLiteral("Network"), QStringLiteral("Internet")},
            {QStringLiteral("Office"), QStringLiteral("Office")},
            {QStringLiteral("Science"), QStringLiteral("Science")},
            {QStringLiteral("System"), QStringLiteral("System")},
            {QStringLiteral("Utility"), QStringLiteral("Utilities")},
        };
        QVariantList out;
        for (const auto &c : list)
            out << QVariantMap{{QStringLiteral("id"), c.first}, {QStringLiteral("title"), c.second}};
        return out;
    }

    Q_INVOKABLE QVariantList search(const QString &query, const QString &category) const
    {
        const QString q = query.trimmed().toLower();
        QVariantList out;
        QList<const App *> hits;
        for (const App &app : m_apps) {
            if (!category.isEmpty() && !app.categories.contains(category))
                continue;
            if (!q.isEmpty()
                && !(app.name.toLower().contains(q) || app.summary.toLower().contains(q)
                     || app.id.toLower().contains(q)))
                continue;
            hits << &app;
        }
        // Name matches first, then verified publishers, then alphabetical.
        std::sort(hits.begin(), hits.end(), [&](const App *a, const App *b) {
            const bool an = a->name.toLower().startsWith(q), bn = b->name.toLower().startsWith(q);
            if (an != bn)
                return an;
            if (a->verified != b->verified)
                return a->verified;
            return a->name.toLower() < b->name.toLower();
        });
        for (const App *app : hits.mid(0, 80))
            out << toMap(*app);
        return out;
    }

    Q_INVOKABLE QVariantMap details(const QString &id) const
    {
        for (const App &app : m_apps)
            if (app.id == id)
                return toMap(app);
        return {};
    }

    // Permissions from the app's sandbox metadata, read from Flathub (needs the network)
    // or from the installed app. Delivered through permissionsReady().
    Q_INVOKABLE void loadPermissions(const QString &id)
    {
        auto *process = new QProcess(this);
        const QStringList arguments = m_installed.contains(id)
            ? QStringList{QStringLiteral("info"), QStringLiteral("--user"), QStringLiteral("--show-metadata"), id}
            : QStringList{QStringLiteral("remote-info"), QStringLiteral("--user"), QStringLiteral("--show-metadata"),
                          QStringLiteral("flathub"), id};
        connect(process, &QProcess::finished, this, [this, process, id](int code) {
            const QString out = QString::fromUtf8(process->readAllStandardOutput());
            if (code == 0)
                Q_EMIT permissionsReady(id, permissionsFromMetadata(out));
            else
                Q_EMIT permissionsReady(id, {permission(
                    explain(QString::fromUtf8(process->readAllStandardError()),
                            QStringLiteral("The permissions could not be read")),
                    QStringLiteral("unknown"))});
            process->deleteLater();
        });
        process->start(QStringLiteral("flatpak"), arguments);
    }

    Q_INVOKABLE void refresh()
    {
        run(QStringLiteral("Updating the catalogue…"),
            {QStringLiteral("update"), QStringLiteral("--user"), QStringLiteral("--appstream"), QStringLiteral("flathub")},
            [this] { loadCatalogue(); });
    }

    Q_INVOKABLE void install(const QString &id)
    {
        run(QStringLiteral("Installing…"),
            {QStringLiteral("install"), QStringLiteral("--user"), QStringLiteral("--noninteractive"), QStringLiteral("-y"),
             QStringLiteral("flathub"), id},
            [this] { loadInstalled(); });
    }

    Q_INVOKABLE void remove(const QString &id)
    {
        run(QStringLiteral("Removing…"),
            {QStringLiteral("uninstall"), QStringLiteral("--user"), QStringLiteral("--noninteractive"), QStringLiteral("-y"), id},
            [this] { loadInstalled(); });
    }

    Q_INVOKABLE void update(const QString &id)
    {
        QStringList arguments{QStringLiteral("update"), QStringLiteral("--user"), QStringLiteral("--noninteractive"), QStringLiteral("-y")};
        if (!id.isEmpty())
            arguments << id;
        run(QStringLiteral("Updating…"), arguments, [this] {
            loadInstalled();
            checkUpdates();
        });
    }

    Q_INVOKABLE void launch(const QString &id) const
    {
        QProcess::startDetached(QStringLiteral("flatpak"), {QStringLiteral("run"), id});
    }

    Q_INVOKABLE void loadInstalled()
    {
        QProcess process;
        process.start(QStringLiteral("flatpak"),
                      {QStringLiteral("list"), QStringLiteral("--user"), QStringLiteral("--app"),
                       QStringLiteral("--columns=application")});
        process.waitForFinished(30000);
        m_installed = QString::fromUtf8(process.readAllStandardOutput())
                          .split(QLatin1Char('\n'), Qt::SkipEmptyParts);
        Q_EMIT installedChanged();
    }

    // Which installed apps have updates (needs the network). Never installs them.
    Q_INVOKABLE void checkUpdates()
    {
        auto *process = new QProcess(this);
        connect(process, &QProcess::finished, this, [this, process](int code) {
            if (code == 0) {
                m_updates = QString::fromUtf8(process->readAllStandardOutput())
                                .split(QLatin1Char('\n'), Qt::SkipEmptyParts);
                Q_EMIT updatesChanged();
            }
            process->deleteLater();
        });
        process->start(QStringLiteral("flatpak"),
                       {QStringLiteral("remote-ls"), QStringLiteral("--user"), QStringLiteral("--updates"),
                        QStringLiteral("--app"), QStringLiteral("--columns=application"), QStringLiteral("flathub")});
    }

    Q_INVOKABLE void loadCatalogue()
    {
        QByteArray xml;
        QFile plain(appstreamDir() + QStringLiteral("/appstream.xml"));
        if (plain.open(QIODevice::ReadOnly)) {
            xml = plain.readAll();
        } else {
            QProcess gunzip;
            gunzip.start(QStringLiteral("gzip"),
                         {QStringLiteral("-dc"), appstreamDir() + QStringLiteral("/appstream.xml.gz")});
            gunzip.waitForFinished(60000);
            xml = gunzip.readAllStandardOutput();
        }
        m_apps = parse(xml);
        Q_EMIT catalogueChanged();
    }

Q_SIGNALS:
    void busyChanged();
    void statusChanged();
    void progressChanged();
    void errorChanged();
    void catalogueChanged();
    void installedChanged();
    void updatesChanged();
    void permissionsReady(const QString &id, const QVariantList &permissions);
    void finished(bool ok);

private:
    // Flatpak's messages, said plainly.
    static QString explain(const QString &stderrText, const QString &fallback)
    {
        const QString e = stderrText.toLower();
        if (e.contains(QLatin1String("could not resolve")) || e.contains(QLatin1String("unable to connect"))
            || e.contains(QLatin1String("could not connect")) || e.contains(QLatin1String("connection refused"))
            || e.contains(QLatin1String("network")) || e.contains(QLatin1String("timeout")))
            return QStringLiteral("No internet connection. Check the network and try again.");
        if (e.contains(QLatin1String("no space left")) || e.contains(QLatin1String("not enough")))
            return QStringLiteral("Not enough disk space. Remove files or applications and try again.");
        if (e.contains(QLatin1String("gpg")) || e.contains(QLatin1String("signature")))
            return QStringLiteral("The signature check failed, so nothing was installed.");
        if (e.contains(QLatin1String("nothing matches")) || e.contains(QLatin1String("not found")))
            return QStringLiteral("Flathub does not offer this application (any more).");
        const QString last = stderrText.trimmed().section(QLatin1Char('\n'), -1);
        return last.isEmpty() ? fallback : fallback + QStringLiteral(": ") + last;
    }

    void run(const QString &status, const QStringList &arguments, std::function<void()> done)
    {
        if (m_job) {
            setError(QStringLiteral("Please wait until the current task has finished."));
            return;
        }
        setError(QString());
        m_status = status;
        m_progress = 0;
        Q_EMIT statusChanged();
        Q_EMIT progressChanged();
        m_job = new QProcess(this);
        m_job->setProcessChannelMode(QProcess::SeparateChannels);
        connect(m_job, &QProcess::readyReadStandardOutput, this, [this] {
            const QString chunk = QString::fromUtf8(m_job->readAllStandardOutput());
            static const QRegularExpression percent(QStringLiteral("(\\d{1,3})%"));
            auto it = percent.globalMatch(chunk);
            while (it.hasNext()) {
                const int value = it.next().captured(1).toInt();
                if (value >= 0 && value <= 100 && value != m_progress) {
                    m_progress = value;
                    Q_EMIT progressChanged();
                }
            }
        });
        connect(m_job, &QProcess::finished, this, [this, done](int code, QProcess::ExitStatus how) {
            const bool ok = how == QProcess::NormalExit && code == 0;
            if (!ok)
                setError(explain(QString::fromUtf8(m_job->readAllStandardError()),
                                 QStringLiteral("That did not work")));
            m_job->deleteLater();
            m_job = nullptr;
            m_status = ok ? QStringLiteral("Done") : QString();
            m_progress = ok ? 100 : 0;
            Q_EMIT statusChanged();
            Q_EMIT progressChanged();
            Q_EMIT busyChanged();
            done();
            Q_EMIT finished(ok);
        });
        m_job->start(QStringLiteral("flatpak"), arguments);
        Q_EMIT busyChanged();
    }

    void setError(const QString &message)
    {
        m_error = message;
        Q_EMIT errorChanged();
    }

    QVariantMap toMap(const App &app) const
    {
        const QString iconPath = appstreamDir() + QStringLiteral("/icons/128x128/") + app.icon;
        return {
            {QStringLiteral("id"), app.id},
            {QStringLiteral("name"), app.name},
            {QStringLiteral("summary"), app.summary},
            {QStringLiteral("description"), app.description},
            {QStringLiteral("developer"), app.developer},
            {QStringLiteral("license"), app.license},
            {QStringLiteral("icon"), QFile::exists(iconPath) ? QStringLiteral("file://") + iconPath : QString()},
            {QStringLiteral("screenshots"), app.screenshots},
            {QStringLiteral("categories"), app.categories},
            {QStringLiteral("verified"), app.verified},
            {QStringLiteral("installed"), m_installed.contains(app.id)},
        };
    }

    static QList<App> parse(const QByteArray &xml)
    {
        QList<App> apps;
        QXmlStreamReader r(xml);
        App app;
        bool inComponent = false, desktop = false, inDescription = false, inScreenshot = false;
        QString customKey;
        while (!r.atEnd()) {
            r.readNext();
            const QString tag = r.name().toString();
            const bool translated = r.attributes().hasAttribute(QStringLiteral("xml:lang"));
            if (r.isStartElement()) {
                if (tag == QLatin1String("component")) {
                    inComponent = true;
                    app = App();
                    const QString type = r.attributes().value(QStringLiteral("type")).toString();
                    desktop = type == QLatin1String("desktop-application") || type == QLatin1String("desktop");
                } else if (!inComponent || translated) {
                    continue;
                } else if (tag == QLatin1String("id") && app.id.isEmpty()) {
                    app.id = r.readElementText().trimmed();
                    if (app.id.endsWith(QLatin1String(".desktop")))
                        app.id.chop(8);
                } else if (tag == QLatin1String("name") && app.name.isEmpty() && !inScreenshot) {
                    app.name = r.readElementText().trimmed();
                } else if (tag == QLatin1String("summary") && app.summary.isEmpty()) {
                    app.summary = r.readElementText().trimmed();
                } else if (tag == QLatin1String("description")) {
                    inDescription = true;
                } else if (inDescription && (tag == QLatin1String("p") || tag == QLatin1String("li"))) {
                    if (app.description.size() < 1500)
                        app.description += (tag == QLatin1String("li") ? QStringLiteral("• ") : QString())
                                           + r.readElementText(QXmlStreamReader::IncludeChildElements).simplified()
                                           + QStringLiteral("\n\n");
                } else if (tag == QLatin1String("developer_name") && app.developer.isEmpty()) {
                    app.developer = r.readElementText().trimmed();
                } else if (tag == QLatin1String("project_license")) {
                    app.license = r.readElementText().trimmed();
                } else if (tag == QLatin1String("category")) {
                    app.categories << r.readElementText().trimmed();
                } else if (tag == QLatin1String("icon")
                           && r.attributes().value(QStringLiteral("type")) == QLatin1String("cached")
                           && app.icon.isEmpty()) {
                    app.icon = r.readElementText().trimmed();
                } else if (tag == QLatin1String("screenshot")) {
                    inScreenshot = true;
                } else if (inScreenshot && tag == QLatin1String("image")
                           && r.attributes().value(QStringLiteral("type")) == QLatin1String("source")
                           && app.screenshots.size() < 3) {
                    app.screenshots << r.readElementText().trimmed();
                } else if (tag == QLatin1String("value")) {
                    customKey = r.attributes().value(QStringLiteral("key")).toString();
                    const QString value = r.readElementText().trimmed();
                    if (customKey == QLatin1String("flathub::verification::verified"))
                        app.verified = value == QLatin1String("true");
                }
            } else if (r.isEndElement()) {
                if (tag == QLatin1String("component")) {
                    inComponent = false;
                    if (desktop && !app.id.isEmpty() && !app.name.isEmpty())
                        apps << app;
                } else if (tag == QLatin1String("description")) {
                    inDescription = false;
                } else if (tag == QLatin1String("screenshot")) {
                    inScreenshot = false;
                }
            }
        }
        return apps;
    }

    QList<App> m_apps;
    QStringList m_installed, m_updates;
    QProcess *m_job = nullptr;
    QString m_status, m_error;
    int m_progress = 0;
};

// The daily user timer: tell the user that updates exist; never apply them.
static int checkUpdatesAndNotify()
{
    QProcess process;
    process.start(QStringLiteral("flatpak"),
                  {QStringLiteral("remote-ls"), QStringLiteral("--user"), QStringLiteral("--updates"),
                   QStringLiteral("--app"), QStringLiteral("--columns=name"), QStringLiteral("flathub")});
    if (!process.waitForFinished(120000) || process.exitCode() != 0)
        return 0;  // offline or Flathub unreachable: say nothing
    const QStringList names = QString::fromUtf8(process.readAllStandardOutput())
                                  .split(QLatin1Char('\n'), Qt::SkipEmptyParts);
    if (names.isEmpty())
        return 0;
    QDBusMessage notify = QDBusMessage::createMethodCall(
        QStringLiteral("org.freedesktop.Notifications"), QStringLiteral("/org/freedesktop/Notifications"),
        QStringLiteral("org.freedesktop.Notifications"), QStringLiteral("Notify"));
    notify << QStringLiteral("AEGIS App Center") << uint(0) << QStringLiteral("aegis-appcenter")
           << QStringLiteral("Application updates available")
           << QStringLiteral("%1 can be updated: %2. Open the App Center to update when you like.")
                  .arg(names.size() == 1 ? QStringLiteral("One application") : QStringLiteral("%1 applications").arg(names.size()),
                       names.mid(0, 4).join(QStringLiteral(", ")))
           << QStringList() << QVariantMap() << int(-1);
    QDBusConnection::sessionBus().call(notify);
    return 0;
}

int main(int argc, char *argv[])
{
    QGuiApplication app(argc, argv);
    QGuiApplication::setApplicationName(QStringLiteral("aegis-appcenter"));
    QGuiApplication::setApplicationDisplayName(QStringLiteral("AEGIS App Center"));
    QGuiApplication::setDesktopFileName(QStringLiteral("org.aegisos.appcenter"));
    if (app.arguments().contains(QStringLiteral("--check-updates")))
        return checkUpdatesAndNotify();

    AppCenter center;
    center.loadInstalled();
    center.loadCatalogue();

    QQuickStyle::setStyle(QStringLiteral("Basic"));
    QQmlApplicationEngine engine;
    engine.rootContext()->setContextProperty(QStringLiteral("center"), &center);
    QObject::connect(&engine, &QQmlApplicationEngine::objectCreationFailed, &app,
                     [] { QCoreApplication::exit(1); }, Qt::QueuedConnection);
    engine.loadFromModule("AegisAppCenter", "Main");
    // Fresh catalogue and update check in the background (needs the network).
    QTimer::singleShot(500, &center, [&center] {
        if (center.catalogueSize() == 0)
            center.refresh();
        center.checkUpdates();
    });
    return app.exec();
}

#include "main.moc"
