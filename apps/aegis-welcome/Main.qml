// Welcome to AEGIS (v3, M11): the window, the scene sequence and the controls.
//
// Seven scenes, each an Item with `ready` (its exercises are done or skipped). Back,
// Next and Skip tour are always available; the progress dots show where the user is.
// Keyboard: Tab between controls, Enter for the focused control, Alt+Left / Alt+Right
// for Back / Next, Escape asks whether to leave the tour. Every animation duration goes
// through motion(): zero when reduced motion is on (KDE's setting or the switch here).
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
import AegisWelcome

ApplicationWindow {
    id: window
    visible: true
    width: Math.min(1040, Screen.desktopAvailableWidth - 80)
    height: Math.min(680, Screen.desktopAvailableHeight - 140)
    minimumWidth: 760
    minimumHeight: 560
    title: "Welcome to AEGIS"
    color: "#0a1220"

    readonly property color accent: "#4fd1e8"
    readonly property color text: "#eef6fb"
    readonly property color muted: "#a9b8c6"
    readonly property color ok: "#5fd39a"
    readonly property string family: "Inter"
    readonly property var titles: ["AEGIS awakens", "Meet your desktop", "Control your workspace",
                                   "Make it yours", "Explore applications", "Security and privacy",
                                   "You're ready"]
    property bool confirmLeave: false

    function motion(ms) { return welcome.reducedMotion ? 0 : ms; }
    function next() {
        if (welcome.scene < titles.length - 1) {
            welcome.scene = welcome.scene + 1;
        } else {
            welcome.finish(false);
            Qt.quit();
        }
    }
    function back() {
        if (welcome.scene > 0) welcome.scene = welcome.scene - 1;
    }
    function leave() {
        welcome.finish(true);
        Qt.quit();
    }

    background: Rectangle {
        gradient: Gradient {
            GradientStop { position: 0.0; color: "#0b1a2e" }
            GradientStop { position: 0.6; color: "#0e1628" }
            GradientStop { position: 1.0; color: "#160f33" }
        }
        // Slow drifting light, absent with reduced motion or Performance Glass.
        Rectangle {
            width: parent.width * 0.8; height: width; radius: width / 2
            color: Qt.rgba(0.31, 0.82, 0.91, 0.06)
            x: parent.width * 0.5
            y: -parent.height * 0.55
            visible: !welcome.reducedMotion && !welcome.lite
            SequentialAnimation on opacity {
                running: !welcome.reducedMotion && !welcome.lite
                loops: Animation.Infinite
                NumberAnimation { from: 0.6; to: 1; duration: 5000; easing.type: Easing.InOutQuad }
                NumberAnimation { from: 1; to: 0.6; duration: 5000; easing.type: Easing.InOutQuad }
            }
        }
    }

    Shortcut { sequences: ["Alt+Right"]; onActivated: window.next() }
    Shortcut { sequences: ["Alt+Left"]; onActivated: window.back() }
    Shortcut {
        sequences: [StandardKey.Cancel]
        onActivated: window.confirmLeave = !window.confirmLeave
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 28
        spacing: 16

        RowLayout {
            Layout.fillWidth: true
            AegisMark { Layout.preferredWidth: 30; Layout.preferredHeight: 34; progress: 1 }
            Label {
                text: window.titles[welcome.scene]
                color: window.text
                font { family: window.family; pixelSize: 22; weight: Font.DemiBold }
                Accessible.role: Accessible.Heading
                Layout.leftMargin: 8
            }
            Item { Layout.fillWidth: true }
            Switch {
                id: reduced
                text: "Reduce motion"
                checked: welcome.reducedMotion
                onToggled: welcome.reducedMotion = checked
                Accessible.name: "Reduce motion"
                contentItem: Label {
                    text: reduced.text; color: window.muted
                    leftPadding: reduced.indicator.width + 6
                    verticalAlignment: Text.AlignVCenter
                    font.family: window.family
                }
            }
        }

        // --- the scenes ------------------------------------------------------------------
        Item {
            id: stage
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true

            Repeater {
                id: scenes
                model: [awakens, desktop, workspace, yours, apps, security, ready]
                delegate: Loader {
                    id: holder
                    required property var modelData
                    required property int index
                    anchors.fill: parent
                    sourceComponent: modelData
                    active: Math.abs(welcome.scene - index) <= 1
                    visible: opacity > 0
                    opacity: welcome.scene === index ? 1 : 0
                    enabled: welcome.scene === index
                    transform: Translate {
                        x: (holder.index - welcome.scene) * 60
                        Behavior on x { NumberAnimation { duration: (welcome.reducedMotion ? 0 : 420); easing.type: Easing.OutCubic } }
                    }
                    Behavior on opacity { NumberAnimation { duration: (welcome.reducedMotion ? 0 : 320); easing.type: Easing.InOutQuad } }
                }
            }
        }

        // --- controls --------------------------------------------------------------------
        RowLayout {
            Layout.fillWidth: true
            spacing: 10
            Button {
                text: "Skip tour"
                Accessible.name: "Skip the tour"
                onClicked: window.confirmLeave = true
            }
            Item { Layout.fillWidth: true }
            Row {
                spacing: 8
                Repeater {
                    model: window.titles.length
                    delegate: Rectangle {
                        required property int index
                        width: index === welcome.scene ? 22 : 8
                        height: 8; radius: 4
                        color: index <= welcome.scene ? window.accent : Qt.rgba(1, 1, 1, 0.22)
                        Behavior on width { NumberAnimation { duration: (welcome.reducedMotion ? 0 : 200) } }
                    }
                }
                Accessible.name: "Scene " + (welcome.scene + 1) + " of " + window.titles.length
            }
            Item { Layout.fillWidth: true }
            Button {
                text: "Back"
                enabled: welcome.scene > 0
                Accessible.name: "Back"
                onClicked: window.back()
            }
            Button {
                id: nextButton
                text: welcome.scene === window.titles.length - 1 ? "Start using AEGIS" : "Next"
                Accessible.name: text
                highlighted: true
                onClicked: window.next()
            }
        }
    }

    // --- leave the tour? -----------------------------------------------------------------
    Rectangle {
        anchors.fill: parent
        visible: window.confirmLeave
        color: Qt.rgba(0, 0, 0, 0.55)
        MouseArea { anchors.fill: parent }
        Glass {
            anchors.centerIn: parent
            width: 460; height: 210
            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 24
                spacing: 12
                Label {
                    text: "Leave the tour?"
                    color: window.text
                    font { family: window.family; pixelSize: 20; weight: Font.DemiBold }
                }
                Label {
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                    color: window.muted
                    font.family: window.family
                    text: "You can start it again at any time: launcher → Welcome to AEGIS."
                }
                RowLayout {
                    Layout.alignment: Qt.AlignRight
                    Button {
                        id: stay
                        text: "Stay"
                        focus: window.confirmLeave
                        onClicked: window.confirmLeave = false
                    }
                    Button { text: "Leave the tour"; onClicked: window.leave() }
                }
            }
        }
    }

    Component { id: awakens; Awakens {} }
    Component { id: desktop; Desktop {} }
    Component { id: workspace; Workspace {} }
    Component { id: yours; MakeItYours {} }
    Component { id: apps; Apps {} }
    Component { id: security; Security {} }
    Component { id: ready; Ready {} }

    Component.onCompleted: nextButton.forceActiveFocus()
}
