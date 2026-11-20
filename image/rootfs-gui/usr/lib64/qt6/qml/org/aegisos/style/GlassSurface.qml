// The one AEGIS glass primitive: tint, light-facing border, inner highlight and a soft
// shadow, built from plain rectangles (cheap on every renderer, no shader passes). The
// blur behind it comes from KWin when the containing window or popup is translucent.
import QtQuick

Item {
    id: surface

    property string material: "regular"   // regular | elevated | control
    property int radius: Tokens.radius.large
    property bool hovered: false
    property bool pressed: false
    default property alias content: contentItem.data
    property alias contentItem: contentItem
    property int padding: Tokens.spacing.medium

    readonly property var materialValues: Tokens.material(material)

    // Soft ambient shadow: three widening, fading outlines.
    Repeater {
        model: surface.materialValues.shadowOpacity > 0 ? 3 : 0
        Rectangle {
            required property int index
            anchors.fill: parent
            anchors.margins: -(index + 1) * Tokens.shadow.ambientSpread / 3
            anchors.topMargin: anchors.margins + Tokens.shadow.offsetY
            radius: surface.radius + (index + 1) * Tokens.shadow.ambientSpread / 3
            color: "transparent"
            border.width: Tokens.shadow.ambientSpread / 3
            border.color: Qt.rgba(0, 0, 0, surface.materialValues.shadowOpacity / (index + 2))
        }
    }

    Rectangle {
        id: fill
        anchors.fill: parent
        radius: surface.radius
        color: surface.materialValues.fill
        border.width: 1
        border.color: surface.materialValues.border
        opacity: surface.enabled ? 1 : Tokens.opacity.disabled

        // State feedback through a brighter inner fill, not colour alone.
        Rectangle {
            anchors.fill: parent
            radius: parent.radius
            color: Tokens.color.cyanBright
            opacity: surface.pressed ? 0.16 : surface.hovered ? 0.08 : 0
            Behavior on opacity {
                NumberAnimation { duration: Tokens.duration(Tokens.motion.fast); easing.type: Tokens.motion.easing }
            }
        }

        // Inner highlight along the light-facing (top) edge.
        Rectangle {
            anchors { left: parent.left; right: parent.right; top: parent.top; margins: 1 }
            height: Math.min(parent.height / 2, surface.radius * 2)
            radius: surface.radius - 1
            gradient: Gradient {
                GradientStop { position: 0; color: surface.materialValues.highlight }
                GradientStop { position: 1; color: "transparent" }
            }
        }
    }

    Item {
        id: contentItem
        anchors.fill: parent
        anchors.margins: surface.padding
    }
}
