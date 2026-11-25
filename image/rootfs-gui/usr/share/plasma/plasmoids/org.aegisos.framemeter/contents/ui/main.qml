/*
 * AEGIS Frame Meter (GUI v2). Animates a large part of its window continuously and
 * records the interval between frames that Qt Quick actually presented (frameSwapped),
 * after a 3 s warm-up, over 10 s. Under Wayland a client may draw a frame only when the
 * compositor asks for one, so the rate it reaches measures the whole path: Qt Quick
 * rendering, KWin compositing and presentation. Results go to the window and, as one
 * line starting with AEGIS-FRAMES, to the user journal (graphics-report reads it).
 */
import QtQuick
import QtQuick.Layouts
import QtQuick.Window
import org.kde.plasma.plasmoid

PlasmoidItem {
    id: root

    switchWidth: 1
    switchHeight: 1
    preferredRepresentation: fullRepresentation

    fullRepresentation: Item {
        id: stage
        Layout.preferredWidth: 960
        Layout.preferredHeight: 600

        property real started: 0
        property real last: 0
        property var intervals: []
        property string result: "measuring…"
        property bool done: false

        function finish() {
            const sorted = intervals.slice().sort((a, b) => a - b);
            const n = sorted.length;
            const total = intervals.reduce((a, b) => a + b, 0);
            const pick = q => sorted[Math.min(n - 1, Math.floor(q * n))];
            const slow = intervals.filter(v => v > 33.4).length;
            result = "frames=" + n + " seconds=" + (total / 1000).toFixed(1)
                + " fps=" + (n / (total / 1000)).toFixed(1)
                + " p50_ms=" + pick(0.5).toFixed(1) + " p95_ms=" + pick(0.95).toFixed(1)
                + " max_ms=" + sorted[n - 1].toFixed(1) + " over_33ms=" + slow
                + " backend=" + GraphicsInfo.api;
            console.log("AEGIS-FRAMES " + result);
            done = true;
        }

        Connections {
            target: stage.Window.window
            function onFrameSwapped() {
                const now = Date.now();
                if (stage.done)
                    return;
                if (stage.started === 0)
                    stage.started = now;
                if (now - stage.started > 3000 && stage.last > 0)
                    stage.intervals.push(now - stage.last);
                stage.last = now;
                if (now - stage.started > 13000 && stage.intervals.length > 0)
                    stage.finish();
            }
        }

        Rectangle {
            anchors.fill: parent
            gradient: Gradient {
                GradientStop { position: 0; color: "#0b1a2e" }
                GradientStop { position: 1; color: "#123a5a" }
            }
        }
        Repeater {
            model: 6
            Rectangle {
                required property int index
                width: stage.width * 0.28
                height: width
                radius: width / 4
                color: Qt.hsla(0.53 + index * 0.03, 0.8, 0.55, 0.55)
                y: stage.height * (0.1 + 0.12 * index)
                NumberAnimation on x {
                    from: -stage.width * 0.3
                    to: stage.width
                    duration: 1600 + 230 * index
                    loops: Animation.Infinite
                }
                RotationAnimation on rotation {
                    from: 0
                    to: 360
                    duration: 2400
                    loops: Animation.Infinite
                }
            }
        }
        Text {
            anchors.centerIn: parent
            color: "white"
            font.pixelSize: 22
            text: "AEGIS Frame Meter\n" + stage.result
            horizontalAlignment: Text.AlignHCenter
        }
    }
}
