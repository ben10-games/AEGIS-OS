// Scene 7, You're ready: rings of light open around the AEGIS mark, a summary of what
// was practised, and the way back to this tour. "Start using AEGIS" (bottom right)
// finishes the tour.
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import AegisWelcome

Item {
    id: scene
    property real t: welcome.reducedMotion ? 1 : 0
    NumberAnimation on t { running: !welcome.reducedMotion; from: 0; to: 1; duration: 1600; easing.type: Easing.OutCubic }

    Repeater {
        model: welcome.lite ? 1 : 3
        delegate: Rectangle {
            required property int index
            anchors.centerIn: mark
            width: (140 + index * 90) * scene.t
            height: width
            radius: width / 2
            color: "transparent"
            border.color: Qt.rgba(0.31, 0.82, 0.91, 0.5 - index * 0.13)
            border.width: 2
            opacity: 1 - scene.t * 0.4
        }
    }
    AegisMark {
        id: mark
        anchors.centerIn: parent
        anchors.verticalCenterOffset: -60
        width: 110; height: 125
        progress: 1
    }
    ColumnLayout {
        anchors { top: mark.bottom; horizontalCenter: parent.horizontalCenter; topMargin: 40 }
        spacing: 8
        opacity: scene.t
        Label {
            Layout.alignment: Qt.AlignHCenter
            text: "You're ready."
            color: "#eef6fb"
            font { family: "Inter"; pixelSize: 34; weight: Font.Light }
        }
        Label {
            Layout.alignment: Qt.AlignHCenter
            text: welcome.completed.length + " of 14 exercises done"
            color: "#5fd39a"
            font { family: "Inter"; pixelSize: 15 }
        }
        Label {
            Layout.alignment: Qt.AlignHCenter
            text: "Come back any time: launcher → Welcome to AEGIS."
            color: "#a9b8c6"
            font { family: "Inter"; pixelSize: 14 }
        }
    }
}
