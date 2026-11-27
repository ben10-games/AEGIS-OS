// One exercise in a scene: what to do, the keyboard way, a done mark. "Show me" reveals
// the hint; "Skip step" marks it done without doing it (never required to go on).
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Glass {
    id: step
    property string key
    property string title
    property string hint
    readonly property bool done: welcome.completed.indexOf(key) >= 0
    property bool showHint: false

    implicitHeight: column.implicitHeight + 24
    Layout.fillWidth: true
    radius: 14
    tint: done ? 0.55 : 0.72
    Accessible.name: title + (done ? ", done" : "")

    // Text on top, the buttons on their own row underneath: fits any width, including the
    // narrow side panel of "Control your workspace" (buttons were cut off there).
    ColumnLayout {
        id: column
        anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter
                  margins: 14 }
        spacing: 6
        RowLayout {
            Layout.fillWidth: true
            spacing: 12
            Rectangle {
                Layout.alignment: Qt.AlignTop
                width: 26; height: 26; radius: 13
                color: step.done ? "#5fd39a" : "transparent"
                border.color: step.done ? "#5fd39a" : Qt.rgba(1, 1, 1, 0.35)
                border.width: 2
                Label {
                    anchors.centerIn: parent
                    text: step.done ? "✓" : ""
                    color: "#06202b"
                    font.bold: true
                }
                Behavior on color { ColorAnimation { duration: (welcome.reducedMotion ? 0 : 250) } }
                scale: step.done ? 1 : 0.92
                Behavior on scale { NumberAnimation { duration: (welcome.reducedMotion ? 0 : 300); easing.type: Easing.OutBack } }
            }
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2
                Label {
                    Layout.fillWidth: true
                    text: step.title
                    color: "#eef6fb"
                    wrapMode: Text.WordWrap
                    font { family: "Inter"; pixelSize: 15; weight: Font.DemiBold }
                }
                Label {
                    Layout.fillWidth: true
                    visible: step.showHint && !step.done
                    text: step.hint
                    color: "#9ff3ff"
                    wrapMode: Text.WordWrap
                    font { family: "Inter"; pixelSize: 13 }
                }
            }
        }
        RowLayout {
            Layout.alignment: Qt.AlignRight
            visible: !step.done
            spacing: 8
            Button {
                text: step.showHint ? "Hide" : "Show me"
                Accessible.name: (step.showHint ? "Hide hint for " : "Show me how to ") + step.title
                onClicked: step.showHint = !step.showHint
            }
            Button {
                text: "Skip step"
                Accessible.name: "Skip step: " + step.title
                onClicked: welcome.complete(step.key)
            }
        }
    }
}
