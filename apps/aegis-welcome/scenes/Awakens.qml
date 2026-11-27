// Scene 1, AEGIS awakens: the mark assembles from glass shards over drifting glass panes,
// then the greeting. About six seconds; any key or click continues at once. With reduced
// motion the mark is simply there.
import QtQuick
import QtQuick.Controls
import AegisWelcome

Item {
    id: scene
    property real progress: welcome.reducedMotion ? 1 : 0

    NumberAnimation on progress {
        running: !welcome.reducedMotion
        from: 0; to: 1
        duration: 3200
        easing.type: Easing.OutCubic
    }

    // Three glass panes at different depths drift slightly (parallax).
    Repeater {
        model: welcome.lite ? 1 : 3
        delegate: Glass {
            required property int index
            width: scene.width * (0.34 - index * 0.06)
            height: width * 0.62
            radius: 26
            tint: 0.25 + index * 0.1
            x: scene.width * (0.08 + index * 0.27) + (1 - scene.progress) * (index - 1) * 80
            y: scene.height * (0.12 + (index % 2) * 0.46) - (1 - scene.progress) * 30
            opacity: 0.35 + 0.25 * scene.progress
        }
    }

    AegisMark {
        id: logo
        anchors.centerIn: parent
        anchors.verticalCenterOffset: -50
        width: 150; height: 170
        progress: scene.progress
        scale: 0.85 + 0.15 * scene.progress
    }
    Label {
        anchors { top: logo.bottom; horizontalCenter: parent.horizontalCenter; topMargin: 26 }
        text: "Welcome to AEGIS"
        color: "#eef6fb"
        opacity: Math.max(0, (scene.progress - 0.6) * 2.5)
        font { family: "Inter"; pixelSize: 40; weight: Font.Light }
    }
    Label {
        anchors { bottom: parent.bottom; horizontalCenter: parent.horizontalCenter; bottomMargin: 8 }
        text: "A few minutes, learning by doing. Press Next (or Alt+→) to begin."
        color: "#a9b8c6"
        opacity: Math.max(0, (scene.progress - 0.8) * 5)
        font { family: "Inter"; pixelSize: 15 }
    }
    MouseArea {
        anchors.fill: parent
        onClicked: scene.progress = 1
    }
    Keys.onPressed: scene.progress = 1
}
