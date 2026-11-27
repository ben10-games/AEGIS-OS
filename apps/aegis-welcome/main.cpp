// Welcome to AEGIS (v3, M11): the interactive first-run tour.
//
// Runs as the logged-in user, with no privileges. Scenes are QML (Main.qml); this file
// holds the state that must be exact:
//   - progress, saved after every change in ~/.local/state/aegis/welcome.json, so a
//     restart or a reboot resumes where the user left off;
//   - the D-Bus object org.aegisos.Welcome /Welcome on the session bus. A small KWin
//     script (watch.js, loaded through KWin's scripting interface) reports real window
//     events to it, so the exercises complete on what the user really does with the
//     desktop. The object also exposes the tour's state read-only (for tests);
//   - reduced motion (KDE's AnimationDurationFactor 0, the app's own switch or
//     --reduced-motion) and the lite visuals used under Performance Glass;
//   - running the few user-level helpers the scenes use (quick-settings, security-status,
//     Dolphin). Nothing here writes outside the user's home.
#include <QDBusConnection>
#include <QDBusInterface>
#include <QDBusReply>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QGuiApplication>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QProcess>
#include <QQmlApplicationEngine>
#include <QQmlContext>
#include <QQuickStyle>
#include <QSaveFile>
#include <QSettings>
#include <QStandardPaths>
#include <QTimer>

static const int StateVersion = 1;
static const int SceneCount = 7;

class Welcome : public QObject
{
    Q_OBJECT
    Q_CLASSINFO("D-Bus Interface", "org.aegisos.Welcome")
    Q_PROPERTY(int scene READ scene WRITE setScene NOTIFY sceneChanged SCRIPTABLE true)
    Q_PROPERTY(QStringList completed READ completed NOTIFY completedChanged SCRIPTABLE true)
    Q_PROPERTY(bool done READ done NOTIFY doneChanged SCRIPTABLE true)
    Q_PROPERTY(bool reducedMotion READ reducedMotion WRITE setReducedMotion NOTIFY reducedMotionChanged SCRIPTABLE true)
    Q_PROPERTY(bool lite READ lite CONSTANT SCRIPTABLE true)
    Q_PROPERTY(bool watching READ watching NOTIFY watchingChanged SCRIPTABLE true)
    Q_PROPERTY(QString lastEvent READ lastEvent NOTIFY lastEventChanged SCRIPTABLE true)

public:
    explicit Welcome(QObject *parent = nullptr) : QObject(parent)
    {
        m_statePath = QStandardPaths::writableLocation(QStandardPaths::GenericStateLocation)
                      + QStringLiteral("/aegis/welcome.json");
        load();
        const QSettings kde(QDir::homePath() + QStringLiteral("/.config/kdeglobals"),
                            QSettings::IniFormat);
        m_systemReducedMotion = kde.value(QStringLiteral("KDE/AnimationDurationFactor"), 1.0)
                                    .toDouble() == 0.0;
        QFile profile(qEnvironmentVariable("XDG_RUNTIME_DIR")
                      + QStringLiteral("/aegis-glass-profile"));
        if (profile.open(QIODevice::ReadOnly))
            m_lite = profile.readAll().trimmed() == "performance";
    }

    int scene() const { return m_scene; }
    QStringList completed() const { return m_completed; }
    bool done() const { return m_done; }
    bool reducedMotion() const { return m_reducedMotion || m_systemReducedMotion; }
    bool lite() const { return m_lite; }
    bool watching() const { return m_watching; }
    QString lastEvent() const { return m_lastEvent; }

    void setScene(int scene)
    {
        scene = qBound(0, scene, SceneCount - 1);
        if (scene == m_scene)
            return;
        m_scene = scene;
        save();
        Q_EMIT sceneChanged();
    }
    void setReducedMotion(bool on)
    {
        if (on == m_reducedMotion)
            return;
        m_reducedMotion = on;
        save();
        Q_EMIT reducedMotionChanged();
    }
    void forceReducedMotion() { m_reducedMotion = true; }

    // Animation durations go through here: zero with reduced motion.
    Q_INVOKABLE int motion(int milliseconds) const
    {
        return reducedMotion() ? 0 : milliseconds;
    }

    Q_INVOKABLE bool isDone(const QString &step) const { return m_completed.contains(step); }

    Q_INVOKABLE void complete(const QString &step)
    {
        if (m_completed.contains(step))
            return;
        m_completed << step;
        save();
        Q_EMIT completedChanged();
    }

    Q_INVOKABLE void finish(bool skipped)
    {
        m_done = true;
        m_skipped = skipped;
        save();
        Q_EMIT doneChanged();
    }

    // Start the tour again from the first scene (the launcher entry, "Replay").
    Q_INVOKABLE void replay()
    {
        m_completed.clear();
        m_done = false;
        m_skipped = false;
        m_scene = 0;
        save();
        Q_EMIT completedChanged();
        Q_EMIT doneChanged();
        Q_EMIT sceneChanged();
    }

    // Read-only facts for the Security scene, from the Security Dashboard's helper.
    Q_INVOKABLE QVariantMap securityFacts() const
    {
        QVariantMap facts;
        const QString out = runAndRead(QStringLiteral("/usr/libexec/aegis/security-status"), {});
        for (const QString &line : out.split(QLatin1Char('\n'))) {
            const int at = line.indexOf(QLatin1Char('='));
            if (at > 0)
                facts.insert(line.left(at), line.mid(at + 1));
        }
        return facts;
    }

    Q_INVOKABLE QString quickSettings(const QStringList &arguments) const
    {
        return runAndRead(QStringLiteral("/usr/libexec/aegis/quick-settings"), arguments);
    }

    // One image per installed wallpaper package (the AEGIS one first), for the live
    // wallpaper preview in "Make it yours".
    Q_INVOKABLE QStringList wallpapers() const
    {
        QStringList found;
        const QDir root(QStringLiteral("/usr/share/wallpapers"));
        QStringList packages = root.entryList(QDir::Dirs | QDir::NoDotAndDotDot, QDir::Name);
        packages.removeAll(QStringLiteral("AEGIS"));
        packages.prepend(QStringLiteral("AEGIS"));
        for (const QString &package : packages) {
            const QDir images(root.filePath(package + QStringLiteral("/contents/images")));
            const QStringList files = images.entryList(
                {QStringLiteral("1920x1080.*"), QStringLiteral("*.png"), QStringLiteral("*.jpg")},
                QDir::Files, QDir::Name);
            if (!files.isEmpty())
                found << images.filePath(files.first());
            if (found.size() == 4)
                break;
        }
        return found;
    }

    Q_INVOKABLE void applyWallpaper(const QString &path) const
    {
        if (path.startsWith(QLatin1String("/usr/share/wallpapers/")))
            QProcess::startDetached(QStringLiteral("plasma-apply-wallpaperimage"), {path});
    }

    Q_INVOKABLE void openFiles() const
    {
        QProcess::startDetached(QStringLiteral("dolphin"), {QDir::homePath()});
    }

    Q_INVOKABLE void openAppCenter() const
    {
        QProcess::startDetached(QStringLiteral("aegis-appcenter"), {});
    }

    // Load the window watcher into KWin. Without it the exercises that need the real
    // desktop offer "Skip step" only; everything else works.
    Q_INVOKABLE void watchWindows()
    {
        QDBusInterface scripting(QStringLiteral("org.kde.KWin"), QStringLiteral("/Scripting"),
                                 QStringLiteral("org.kde.kwin.Scripting"));
        scripting.call(QStringLiteral("unloadScript"), QStringLiteral("aegis-welcome"));
        const QDBusReply<int> id = scripting.call(
            QStringLiteral("loadScript"),
            QStringLiteral("/usr/share/aegis/welcome/watch.js"), QStringLiteral("aegis-welcome"));
        if (!id.isValid() || id.value() < 0) {
            qWarning("aegis-welcome: KWin did not load the window watcher: %s",
                     qPrintable(id.error().message()));
            return;
        }
        QDBusInterface script(QStringLiteral("org.kde.KWin"),
                              QStringLiteral("/Scripting/Script%1").arg(id.value()),
                              QStringLiteral("org.kde.kwin.Script"));
        script.call(QStringLiteral("run"));
        m_watching = true;
        Q_EMIT watchingChanged();
    }

    void unwatch()
    {
        QDBusInterface scripting(QStringLiteral("org.kde.KWin"), QStringLiteral("/Scripting"),
                                 QStringLiteral("org.kde.kwin.Scripting"));
        scripting.call(QStringLiteral("unloadScript"), QStringLiteral("aegis-welcome"));
    }

public Q_SLOTS:
    // Called by watch.js through KWin's callDBus with one JSON object (event, class,
    // geometry, work area, flags): a single string keeps the D-Bus signature simple.
    Q_SCRIPTABLE void report(const QString &json)
    {
        const QJsonObject event = QJsonDocument::fromJson(json.toUtf8()).object();
        if (event.isEmpty())
            return;
        m_lastEvent = json;
        Q_EMIT lastEventChanged();
        Q_EMIT windowEvent(event.toVariantMap());
    }

Q_SIGNALS:
    void sceneChanged();
    void completedChanged();
    void doneChanged();
    void reducedMotionChanged();
    void watchingChanged();
    void lastEventChanged();
    void windowEvent(const QVariantMap &event);

private:
    static QString runAndRead(const QString &program, const QStringList &arguments)
    {
        QProcess process;
        process.start(program, arguments);
        if (!process.waitForFinished(15000))
            return QString();
        return QString::fromUtf8(process.readAllStandardOutput());
    }

    void load()
    {
        QFile file(m_statePath);
        if (!file.open(QIODevice::ReadOnly))
            return;
        const QJsonObject state = QJsonDocument::fromJson(file.readAll()).object();
        if (state.value(QStringLiteral("version")).toInt() != StateVersion)
            return;
        m_scene = qBound(0, state.value(QStringLiteral("scene")).toInt(), SceneCount - 1);
        for (const QJsonValue &step : state.value(QStringLiteral("completed")).toArray())
            m_completed << step.toString();
        m_done = state.value(QStringLiteral("done")).toBool();
        m_skipped = state.value(QStringLiteral("skipped")).toBool();
        m_reducedMotion = state.value(QStringLiteral("reducedMotion")).toBool();
    }

    void save() const
    {
        QDir().mkpath(QFileInfo(m_statePath).absolutePath());
        QSaveFile file(m_statePath);
        if (!file.open(QIODevice::WriteOnly))
            return;
        const QJsonObject state{
            {QStringLiteral("version"), StateVersion},
            {QStringLiteral("scene"), m_scene},
            {QStringLiteral("completed"), QJsonArray::fromStringList(m_completed)},
            {QStringLiteral("done"), m_done},
            {QStringLiteral("skipped"), m_skipped},
            {QStringLiteral("reducedMotion"), m_reducedMotion},
        };
        file.write(QJsonDocument(state).toJson());
        file.commit();
    }

    QString m_statePath;
    int m_scene = 0;
    QStringList m_completed;
    bool m_done = false;
    bool m_skipped = false;
    bool m_reducedMotion = false;
    bool m_systemReducedMotion = false;
    bool m_lite = false;
    bool m_watching = false;
    QString m_lastEvent;
};

int main(int argc, char *argv[])
{
    QGuiApplication app(argc, argv);
    QGuiApplication::setApplicationName(QStringLiteral("aegis-welcome"));
    QGuiApplication::setApplicationDisplayName(QStringLiteral("Welcome to AEGIS"));
    QGuiApplication::setDesktopFileName(QStringLiteral("org.aegisos.welcome"));
    const QStringList arguments = app.arguments();

    Welcome welcome;
    // --autostart (first login): only while the tour is not finished or skipped.
    if (arguments.contains(QStringLiteral("--autostart")) && welcome.done())
        return 0;
    if (arguments.contains(QStringLiteral("--replay")) || welcome.done())
        welcome.replay();
    if (arguments.contains(QStringLiteral("--reduced-motion")))
        welcome.forceReducedMotion();

    QDBusConnection bus = QDBusConnection::sessionBus();
    if (!bus.registerService(QStringLiteral("org.aegisos.Welcome"))) {
        qWarning("aegis-welcome: already running");
        return 0;
    }
    bus.registerObject(QStringLiteral("/Welcome"), &welcome,
                       QDBusConnection::ExportScriptableSlots
                           | QDBusConnection::ExportScriptableProperties);

    QQuickStyle::setStyle(QStringLiteral("Basic"));
    QQmlApplicationEngine engine;
    engine.rootContext()->setContextProperty(QStringLiteral("welcome"), &welcome);
    QObject::connect(&engine, &QQmlApplicationEngine::objectCreationFailed, &app,
                     [] { QCoreApplication::exit(1); }, Qt::QueuedConnection);
    engine.loadFromModule("AegisWelcome", "Main");
    QTimer::singleShot(0, &welcome, &Welcome::watchWindows);
    QObject::connect(&app, &QCoreApplication::aboutToQuit, &welcome, &Welcome::unwatch);
    return app.exec();
}

#include "main.moc"
