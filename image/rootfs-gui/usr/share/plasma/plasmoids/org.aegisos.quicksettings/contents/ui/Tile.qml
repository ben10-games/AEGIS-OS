// One Quick Settings tile: a glass control with an icon, a title and a state line. A
// toggle tile is filled with the accent when on. Keyboard: Tab to reach it, Space or
// Enter to activate.
import QtQuick
import QtQuick.Layouts
import org.kde.plasma.components as PlasmaComponents
import org.kde.kirigami as Kirigami
import org.aegisos.style

GlassSurface {
    id: tile

    property string iconName
    property string title
    property string detail
    property bool toggle: false
    property bool checked: false
    signal activated()

    Layout.fillWidth: true
    Layout.preferredHeight: Kirigami.Units.gridUnit * 3.4
    material: "control"
    radius: Tokens.radius.medium
    hovered: area.containsMouse || activeFocus
    pressed: area.pressed
    activeFocusOnTab: true

    Accessible.role: toggle ? Accessible.CheckBox : Accessible.Button
    Accessible.name: title
    Accessible.checkable: toggle
    Accessible.checked: checked
    Accessible.onPressAction: tile.activated()
    Keys.onSpacePressed: tile.activated()
    Keys.onReturnPressed: tile.activated()

    Rectangle {
        anchors.fill: parent
        radius: tile.radius
        color: Kirigami.Theme.highlightColor
        opacity: tile.toggle && tile.checked ? 0.85 : 0
        Behavior on opacity { NumberAnimation { duration: Kirigami.Units.shortDuration } }
    }
    Rectangle {
        anchors.fill: parent
        radius: tile.radius
        color: "transparent"
        border.width: tile.activeFocus ? 2 : 0
        border.color: Kirigami.Theme.focusColor
    }

    RowLayout {
        anchors.fill: parent
        anchors.margins: Tokens.spacing.small
        spacing: Tokens.spacing.small
        Kirigami.Icon {
            source: tile.iconName
            Layout.preferredWidth: Kirigami.Units.iconSizes.smallMedium
            Layout.preferredHeight: Kirigami.Units.iconSizes.smallMedium
            color: tile.toggle && tile.checked ? Kirigami.Theme.highlightedTextColor
                                               : Kirigami.Theme.textColor
            isMask: tile.toggle && tile.checked
        }
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 0
            PlasmaComponents.Label {
                Layout.fillWidth: true
                text: tile.title
                elide: Text.ElideRight
                font.weight: Font.DemiBold
                color: tile.toggle && tile.checked ? Kirigami.Theme.highlightedTextColor
                                                   : Kirigami.Theme.textColor
            }
            PlasmaComponents.Label {
                Layout.fillWidth: true
                visible: text.length > 0
                text: tile.detail
                elide: Text.ElideRight
                opacity: 0.75
                font.pointSize: Kirigami.Theme.smallFont.pointSize
                color: tile.toggle && tile.checked ? Kirigami.Theme.highlightedTextColor
                                                   : Kirigami.Theme.textColor
            }
        }
    }
    MouseArea {
        id: area
        anchors.fill: parent
        hoverEnabled: true
        onClicked: tile.activated()
    }
}
