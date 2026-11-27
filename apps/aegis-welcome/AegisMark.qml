// The AEGIS mark as layered glass: a faceted shield whose six shards fly in and settle
// as `progress` goes from 0 to 1, then an edge light. Drawn with Qt Quick Shapes; with
// progress 1 it is the still mark.
import QtQuick
import QtQuick.Shapes

Item {
    id: mark
    property real progress: 1
    implicitWidth: 120
    implicitHeight: 136

    readonly property real s: Math.min(width / 64, height / 72)

    // Shards of the shield: polygons in a 64x72 box, and the direction they come from.
    readonly property var shards: [
        { pts: [[32, 4], [54, 11], [32, 30]], dx: 40, dy: -50, c: "#1d3b5c" },
        { pts: [[32, 4], [32, 30], [10, 11]], dx: -40, dy: -50, c: "#163150" },
        { pts: [[10, 11], [32, 30], [10, 32]], dx: -70, dy: 0, c: "#12304f" },
        { pts: [[54, 11], [54, 32], [32, 30]], dx: 70, dy: 0, c: "#1a3858" },
        { pts: [[10, 32], [32, 30], [32, 64]], dx: -40, dy: 60, c: "#0e2440" },
        { pts: [[54, 32], [32, 64], [32, 30]], dx: 40, dy: 60, c: "#0b1e36" }
    ]

    Repeater {
        model: mark.shards
        delegate: Shape {
            required property var modelData
            required property int index
            readonly property real local: Math.max(0, Math.min(1, mark.progress * 1.6 - index * 0.1))
            anchors.fill: parent
            opacity: local
            transform: Translate {
                x: (1 - local) * modelData.dx * mark.s
                y: (1 - local) * modelData.dy * mark.s
            }
            ShapePath {
                fillColor: modelData.c
                strokeColor: Qt.rgba(0.62, 0.95, 1.0, 0.35)
                strokeWidth: 1
                startX: modelData.pts[0][0] * mark.s
                startY: modelData.pts[0][1] * mark.s
                PathLine { x: modelData.pts[1][0] * mark.s; y: modelData.pts[1][1] * mark.s }
                PathLine { x: modelData.pts[2][0] * mark.s; y: modelData.pts[2][1] * mark.s }
                PathLine { x: modelData.pts[0][0] * mark.s; y: modelData.pts[0][1] * mark.s }
            }
        }
    }
    // Edge light, once the shards are in place.
    Shape {
        anchors.fill: parent
        opacity: Math.max(0, (mark.progress - 0.8) * 5)
        ShapePath {
            fillColor: "transparent"
            strokeColor: "#4fd1e8"
            strokeWidth: 2.5 * mark.s
            joinStyle: ShapePath.RoundJoin
            startX: 32 * mark.s; startY: 4 * mark.s
            PathLine { x: 54 * mark.s; y: 11 * mark.s }
            PathLine { x: 54 * mark.s; y: 32 * mark.s }
            PathQuad { x: 32 * mark.s; y: 64 * mark.s; controlX: 54 * mark.s; controlY: 54 * mark.s }
            PathQuad { x: 10 * mark.s; y: 32 * mark.s; controlX: 10 * mark.s; controlY: 54 * mark.s }
            PathLine { x: 10 * mark.s; y: 11 * mark.s }
            PathLine { x: 32 * mark.s; y: 4 * mark.s }
        }
    }
}
