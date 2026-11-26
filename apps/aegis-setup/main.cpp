// AEGIS Setup (v3, M8): the first-boot account assistant.
//
// Runs as the unprivileged system user 'aegis-setup' in a KWin-only session that exists
// only until the first account is created. It never changes the system itself: it sends
// one request (full name, user name, password, administrator choice, time zone) over
// the local socket /run/aegis/provision.sock to /usr/libexec/aegis/aegis-provision,
// which validates it, creates the account and refuses every later request.
#include <QGuiApplication>
#include <QJsonDocument>
#include <QJsonObject>
#include <QLocalSocket>
#include <QQmlApplicationEngine>
#include <QQmlContext>
#include <QQuickStyle>
#include <QTimeZone>
#include <QTimer>

class Provisioner : public QObject
{
    Q_OBJECT
public:
    using QObject::QObject;

    Q_INVOKABLE QStringList timeZones() const
    {
        QStringList zones;
        for (const QByteArray &id : QTimeZone::availableTimeZoneIds()) {
            const QString zone = QString::fromLatin1(id);
            if (zone.contains(QLatin1Char('/')) || zone == QLatin1String("UTC"))
                zones << zone;
        }
        zones.removeDuplicates();
        zones.sort();
        return zones;
    }

    Q_INVOKABLE void createAccount(const QString &fullName, const QString &userName,
                                   QString password, bool administrator,
                                   const QString &timeZone)
    {
        auto *socket = new QLocalSocket(this);
        QJsonObject request{{QStringLiteral("full_name"), fullName},
                            {QStringLiteral("user_name"), userName},
                            {QStringLiteral("password"), password},
                            {QStringLiteral("administrator"), administrator},
                            {QStringLiteral("time_zone"), timeZone}};
        QByteArray line = QJsonDocument(request).toJson(QJsonDocument::Compact) + '\n';
        password.fill(QLatin1Char(' '));
        request = QJsonObject();

        connect(socket, &QLocalSocket::connected, socket, [socket, line]() mutable {
            socket->write(line);
            line.fill(' ');
        });
        connect(socket, &QLocalSocket::readyRead, this, [this, socket]() {
            if (!socket->canReadLine())
                return;
            const QJsonObject reply = QJsonDocument::fromJson(socket->readLine()).object();
            Q_EMIT finished(reply.value(QStringLiteral("ok")).toBool(),
                            reply.value(QStringLiteral("message")).toString());
            socket->disconnectFromServer();
            socket->deleteLater();
        });
        connect(socket, &QLocalSocket::errorOccurred, this, [this, socket]() {
            Q_EMIT finished(false, QStringLiteral("The setup service is not available (%1).")
                                       .arg(socket->errorString()));
            socket->deleteLater();
        });
        socket->connectToServer(QStringLiteral("/run/aegis/provision.sock"));
    }

Q_SIGNALS:
    void finished(bool ok, const QString &message);
};

int main(int argc, char *argv[])
{
    QGuiApplication app(argc, argv);
    QGuiApplication::setApplicationName(QStringLiteral("AEGIS Setup"));
    QQuickStyle::setStyle(QStringLiteral("Basic"));

    Provisioner provisioner;
    QQmlApplicationEngine engine;
    engine.rootContext()->setContextProperty(QStringLiteral("provisioner"), &provisioner);
    QObject::connect(&engine, &QQmlApplicationEngine::objectCreationFailed, &app,
                     []() { QCoreApplication::exit(1); }, Qt::QueuedConnection);
    engine.loadFromModule("AegisSetup", "Main");
    return app.exec();
}

#include "main.moc"
