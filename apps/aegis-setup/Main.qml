// AEGIS Setup (v3, M8): first-boot account creation. Full screen, keyboard first:
// Tab moves between fields, Enter in any field creates the account when the form is valid.
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ApplicationWindow {
    id: window
    visible: true
    visibility: Window.FullScreen
    title: "AEGIS Setup"
    color: "#0b1220"

    readonly property color accent: "#38bef0"
    readonly property color text: "#e1e8f2"
    readonly property color muted: "#96a5b9"
    readonly property color danger: "#f05a64"
    property bool busy: false
    property bool done: false
    property bool userNameEdited: false
    property string status: ""

    // The user name suggested from the full name: lower case letters and digits only.
    function suggestedUserName(name) {
        let s = name.toLowerCase().split(/\s+/)[0] || "";
        s = s.replace(/[^a-z0-9]/g, "").slice(0, 32);
        return s.length > 0 && /[0-9]/.test(s[0]) ? "u" + s.slice(0, 31) : s;
    }
    readonly property bool userNameValid: /^[a-z_][a-z0-9_-]{0,31}$/.test(userName.text)
        && ["root", "aegis-setup", "admin", "sddm", "nobody"].indexOf(userName.text) < 0
    readonly property bool passwordLongEnough: password.text.length >= 8
    readonly property bool passwordsMatch: password.text === confirm.text
    readonly property bool valid: fullName.text.trim().length > 0 && fullName.text.indexOf(":") < 0
        && userNameValid && passwordLongEnough && passwordsMatch
        && password.text !== userName.text

    function submit() {
        if (!valid || busy || done)
            return;
        busy = true;
        status = "Creating your account…";
        provisioner.createAccount(fullName.text.trim(), userName.text, password.text,
                                  administrator.checked, timeZone.currentText);
    }

    Connections {
        target: provisioner
        function onFinished(ok, message) {
            window.busy = false;
            window.status = message;
            if (ok) {
                window.done = true;
                password.text = "";
                confirm.text = "";
            }
        }
    }

    background: Rectangle {
        gradient: Gradient {
            GradientStop { position: 0.0; color: "#0b1a2e" }
            GradientStop { position: 0.55; color: "#101a33" }
            GradientStop { position: 1.0; color: "#1b1240" }
        }
        Rectangle {
            width: parent.width * 0.9; height: width; radius: width / 2
            x: parent.width * 0.45; y: -parent.height * 0.6
            color: Qt.rgba(0.22, 0.75, 0.94, 0.07)
        }
    }

    Rectangle {
        id: card
        anchors.centerIn: parent
        width: Math.min(560, window.width - 48)
        height: column.implicitHeight + 64
        radius: 22
        color: Qt.rgba(0.08, 0.12, 0.19, 0.86)
        border.color: Qt.rgba(1, 1, 1, 0.12)
        Rectangle {
            anchors { left: parent.left; right: parent.right; top: parent.top; margins: 1 }
            height: 1; radius: 1; color: Qt.rgba(1, 1, 1, 0.22)
        }

        ColumnLayout {
            id: column
            anchors { fill: parent; margins: 32 }
            spacing: 12

            Label {
                text: "Welcome to AEGIS OS"
                color: window.text
                font.pixelSize: 30
                font.weight: Font.DemiBold
            }
            Label {
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                color: window.muted
                text: "Create the account you will use on this computer. Its password protects "
                    + "your files and is needed for administrator tasks. Nothing is sent anywhere."
            }

            Label { text: "Full name"; color: window.muted }
            TextField {
                id: fullName
                Layout.fillWidth: true
                focus: true
                enabled: !window.busy && !window.done
                placeholderText: "Your name"
                Accessible.name: "Full name"
                onTextChanged: if (!window.userNameEdited) userName.text = window.suggestedUserName(text)
                onAccepted: window.submit()
                KeyNavigation.tab: userName
            }
            Label { text: "User name"; color: window.muted }
            TextField {
                id: userName
                Layout.fillWidth: true
                enabled: !window.busy && !window.done
                placeholderText: "lower case, e.g. alex"
                Accessible.name: "User name"
                validator: RegularExpressionValidator { regularExpression: /[a-z0-9_-]{0,32}/ }
                onTextEdited: window.userNameEdited = true
                onAccepted: window.submit()
                KeyNavigation.tab: password
            }
            Label { text: "Password (at least 8 characters)"; color: window.muted }
            TextField {
                id: password
                Layout.fillWidth: true
                enabled: !window.busy && !window.done
                echoMode: TextInput.Password
                Accessible.name: "Password"
                onAccepted: window.submit()
                KeyNavigation.tab: confirm
            }
            Label { text: "Repeat the password"; color: window.muted }
            TextField {
                id: confirm
                Layout.fillWidth: true
                enabled: !window.busy && !window.done
                echoMode: TextInput.Password
                Accessible.name: "Repeat the password"
                onAccepted: window.submit()
                KeyNavigation.tab: administrator
            }
            CheckBox {
                id: administrator
                checked: true
                enabled: !window.busy && !window.done
                // The Basic style draws the label in the palette's window text colour,
                // which is dark: invisible on the dark card (v3 run 45823217951).
                palette.windowText: window.text
                text: "Administrator (can install system updates and change system settings)"
                Accessible.name: text
                KeyNavigation.tab: timeZone
            }
            RowLayout {
                Layout.fillWidth: true
                Label { text: "Time zone"; color: window.muted }
                ComboBox {
                    id: timeZone
                    Layout.fillWidth: true
                    enabled: !window.busy && !window.done
                    model: provisioner.timeZones()
                    currentIndex: Math.max(0, model.indexOf("UTC"))
                    Accessible.name: "Time zone"
                    KeyNavigation.tab: create
                }
            }
            Label {
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                color: window.done ? window.accent : window.danger
                visible: text.length > 0
                text: window.status.length > 0 ? window.status
                    : (password.text.length > 0 && !window.passwordLongEnough) ? "The password needs at least 8 characters."
                    : (confirm.text.length > 0 && !window.passwordsMatch) ? "The passwords do not match."
                    : (userName.text.length > 0 && !window.userNameValid) ? "This user name cannot be used."
                    : ""
            }
            Button {
                id: create
                Layout.alignment: Qt.AlignRight
                text: window.done ? "Starting the login screen…" : "Create account"
                enabled: window.valid && !window.busy && !window.done
                Accessible.name: "Create account"
                onClicked: window.submit()
                Keys.onReturnPressed: window.submit()
            }
        }
    }
}
