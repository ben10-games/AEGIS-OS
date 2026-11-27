// AEGIS OS login screen (v3, M10), an SDDM greeter theme. Original AEGIS design: the
// AEGIS wallpaper under a dark scrim, the time and date on the left, and a glass card
// with the account and the password field. The password field has the keyboard focus
// from the start: type the password and press Enter. Several accounts: arrows or the
// list choose one. No blur or shader effects (the greeter often renders in software in
// a virtual machine); the glass is drawn: translucent fill, edge light and soft shadow.
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: root
    width: 1920
    height: 1080

    readonly property color accent: "#4fd1e8"
    readonly property color text: "#eef6fb"
    readonly property color muted: "#a9b8c6"
    readonly property color danger: "#ff6b6b"
    readonly property string family: "Inter"
    property int userIndex: Math.max(0, userModel.lastIndex)
    property int sessionIndex: Math.max(0, sessionModel.lastIndex)
    property string message: ""
    property bool busy: false

    function roleOf(index, role) {
        return userModel.data(userModel.index(index, 0), role);
    }
    readonly property string userName: userModel.count > 0
        ? (roleOf(userIndex, Qt.UserRole + 1) || "") : ""
    readonly property string realName: userModel.count > 0
        ? (roleOf(userIndex, Qt.UserRole + 2) || userName) : ""

    function logIn() {
        if (busy || userName.length === 0)
            return;
        busy = true;
        message = "";
        sddm.login(userName, password.text, sessionIndex);
    }

    Connections {
        target: sddm
        function onLoginFailed() {
            root.busy = false;
            root.message = "That password is not right. Try again.";
            password.text = "";
            password.forceActiveFocus();
        }
        function onLoginSucceeded() {
            root.message = "";
        }
    }

    // --- background -----------------------------------------------------------------
    Image {
        anchors.fill: parent
        source: config.background || ""
        fillMode: Image.PreserveAspectCrop
        asynchronous: false
    }
    Rectangle {
        anchors.fill: parent
        gradient: Gradient {
            orientation: Gradient.Horizontal
            GradientStop { position: 0.0; color: Qt.rgba(0.02, 0.05, 0.09, 0.78) }
            GradientStop { position: 0.55; color: Qt.rgba(0.02, 0.05, 0.09, 0.45) }
            GradientStop { position: 1.0; color: Qt.rgba(0.02, 0.05, 0.09, 0.70) }
        }
    }

    // --- time and date --------------------------------------------------------------
    Column {
        anchors { left: parent.left; bottom: parent.bottom; margins: root.height * 0.08 }
        spacing: 4
        Text {
            id: time
            color: root.text
            font { family: root.family; pixelSize: Math.round(root.height * 0.11); weight: Font.Light }
        }
        Text {
            id: date
            color: root.muted
            font { family: root.family; pixelSize: Math.round(root.height * 0.028) }
        }
        Timer {
            interval: 1000
            running: true
            repeat: true
            triggeredOnStart: true
            onTriggered: {
                const now = new Date();
                time.text = Qt.formatTime(now, "hh:mm");
                date.text = Qt.formatDate(now, "dddd d MMMM");
            }
        }
    }

    // --- the card -------------------------------------------------------------------
    Rectangle {
        id: shadow
        anchors.centerIn: card
        anchors.verticalCenterOffset: 10
        width: card.width + 24
        height: card.height + 24
        radius: card.radius + 12
        color: Qt.rgba(0, 0, 0, 0.28)
    }
    Rectangle {
        id: card
        anchors { right: parent.right; verticalCenter: parent.verticalCenter
                  rightMargin: Math.max(48, root.width * 0.12) }
        width: Math.min(440, root.width - 96)
        height: column.implicitHeight + 64
        radius: 26
        color: Qt.rgba(0.07, 0.11, 0.18, 0.72)
        border.color: Qt.rgba(1, 1, 1, 0.14)

        Rectangle {  // edge light along the top
            anchors { left: parent.left; right: parent.right; top: parent.top; margins: 1 }
            height: 1
            color: Qt.rgba(0.62, 0.95, 1.0, 0.35)
        }

        ColumnLayout {
            id: column
            anchors { fill: parent; margins: 32 }
            spacing: 14

            Rectangle {  // the account's initial in a glass disc
                Layout.alignment: Qt.AlignHCenter
                width: 88; height: 88; radius: 44
                color: Qt.rgba(0.31, 0.82, 0.91, 0.16)
                border.color: root.accent
                border.width: 2
                Text {
                    anchors.centerIn: parent
                    text: root.realName.length > 0 ? root.realName[0].toUpperCase() : "A"
                    color: root.text
                    font { family: root.family; pixelSize: 38; weight: Font.DemiBold }
                }
            }
            Text {
                Layout.alignment: Qt.AlignHCenter
                text: root.realName.length > 0 ? root.realName : "AEGIS OS"
                color: root.text
                font { family: root.family; pixelSize: 24; weight: Font.DemiBold }
            }
            Text {
                Layout.alignment: Qt.AlignHCenter
                visible: userModel.count > 1
                text: "‹  " + (root.userIndex + 1) + " of " + userModel.count + "  ›"
                color: root.muted
                font { family: root.family; pixelSize: 13 }
                MouseArea {
                    anchors.fill: parent
                    onClicked: root.userIndex = (root.userIndex + 1) % userModel.count
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                TextField {
                    id: password
                    Layout.fillWidth: true
                    Layout.preferredHeight: 46
                    echoMode: TextInput.Password
                    placeholderText: "Password"
                    enabled: !root.busy
                    focus: true
                    color: root.text
                    placeholderTextColor: root.muted
                    font { family: root.family; pixelSize: 16 }
                    leftPadding: 16
                    background: Rectangle {
                        radius: 14
                        color: Qt.rgba(1, 1, 1, password.activeFocus ? 0.12 : 0.08)
                        border.color: password.activeFocus ? root.accent : Qt.rgba(1, 1, 1, 0.18)
                        border.width: password.activeFocus ? 2 : 1
                    }
                    Accessible.name: "Password for " + root.realName
                    onAccepted: root.logIn()
                    Keys.onUpPressed: root.userIndex = (root.userIndex + userModel.count - 1) % Math.max(1, userModel.count)
                    Keys.onDownPressed: root.userIndex = (root.userIndex + 1) % Math.max(1, userModel.count)
                }
                Button {
                    id: go
                    Layout.preferredWidth: 46
                    Layout.preferredHeight: 46
                    enabled: !root.busy
                    Accessible.name: "Log in"
                    onClicked: root.logIn()
                    contentItem: Text {
                        text: "→"
                        color: "#06202b"
                        font { family: root.family; pixelSize: 22; weight: Font.DemiBold }
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                    background: Rectangle {
                        radius: 14
                        color: go.down ? "#2a9fbd" : root.accent
                    }
                }
            }
            Text {
                Layout.fillWidth: true
                visible: text.length > 0
                text: root.busy ? "Logging in…" : root.message
                color: root.busy ? root.muted : root.danger
                wrapMode: Text.WordWrap
                horizontalAlignment: Text.AlignHCenter
                font { family: root.family; pixelSize: 14 }
            }
        }
    }

    // --- power ----------------------------------------------------------------------
    Row {
        anchors { right: parent.right; bottom: parent.bottom; margins: 28 }
        spacing: 12
        Repeater {
            model: [
                { label: "Restart", visible: sddm.canReboot, action: () => sddm.reboot() },
                { label: "Shut down", visible: sddm.canPowerOff, action: () => sddm.powerOff() }
            ]
            delegate: Button {
                required property var modelData
                visible: modelData.visible
                text: modelData.label
                Accessible.name: modelData.label
                onClicked: modelData.action()
                contentItem: Text {
                    text: parent.text
                    color: root.text
                    font { family: root.family; pixelSize: 14 }
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
                background: Rectangle {
                    implicitWidth: 112
                    implicitHeight: 38
                    radius: 12
                    color: Qt.rgba(1, 1, 1, parent.hovered ? 0.16 : 0.08)
                    border.color: Qt.rgba(1, 1, 1, 0.16)
                }
            }
        }
    }

    Component.onCompleted: password.forceActiveFocus()
}
