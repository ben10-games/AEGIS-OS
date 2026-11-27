// AEGIS Quick Settings (v3, M10): the control centre in the top bar (Meta+A). Dark or
// light, the Liquid Glass profile, Night Light, Do Not Disturb, a screenshot, locking the
// screen and the most used settings pages. Every action runs as the desktop user
// (/usr/libexec/aegis/quick-settings, Spectacle, loginctl, System Settings) and changes
// only that user's own settings; nothing here asks for administrator rights.
import QtQuick
import QtQuick.Layouts
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.components as PlasmaComponents
import org.kde.plasma.plasma5support as P5Support
import org.kde.kirigami as Kirigami
import org.aegisos.style

PlasmoidItem {
    id: root

    readonly property string tool: "/usr/libexec/aegis/quick-settings"
    property var facts: ({})

    Plasmoid.icon: "aegis-quicksettings"
    toolTipMainText: "Quick Settings"
    toolTipSubText: "Appearance, Liquid Glass, Night Light, Do Not Disturb (Meta+A)"
    switchWidth: Kirigami.Units.gridUnit * 18
    switchHeight: Kirigami.Units.gridUnit * 18
    preferredRepresentation: compactRepresentation

    P5Support.DataSource {
        id: executable
        engine: "executable"
        connectedSources: []
        onNewData: (source, data) => {
            if (source === root.tool + " status") {
                const parsed = {};
                for (const line of (data["stdout"] || "").split("\n")) {
                    const at = line.indexOf("=");
                    if (at > 0)
                        parsed[line.slice(0, at)] = line.slice(at + 1);
                }
                root.facts = parsed;
            } else {
                executable.connectSource(root.tool + " status");
            }
            disconnectSource(source);
        }
    }

    function run(command) {
        executable.connectSource(command);
    }
    function launch(command) {
        root.expanded = false;
        executable.connectSource(command);
    }

    onExpandedChanged: if (expanded) run(tool + " status")
    Component.onCompleted: run(tool + " status")

    readonly property bool dark: (facts.scheme || "AEGISDark") !== "AEGISLight"
    readonly property var profiles: [
        { id: "auto", title: "Auto" },
        { id: "full", title: "Full" },
        { id: "balanced", title: "Balanced" },
        { id: "performance", title: "Performance" }
    ]

    fullRepresentation: GlassSurface {
        Layout.minimumWidth: Kirigami.Units.gridUnit * 20
        Layout.preferredWidth: Kirigami.Units.gridUnit * 22
        Layout.preferredHeight: column.implicitHeight + 2 * Tokens.spacing.large
        material: "elevated"
        radius: Tokens.radius.large
        padding: Tokens.spacing.large
        Accessible.name: "Quick Settings"

        ColumnLayout {
            id: column
            anchors.fill: parent
            spacing: Tokens.spacing.medium

            RowLayout {
                Layout.fillWidth: true
                Kirigami.Heading {
                    Layout.fillWidth: true
                    text: "Quick Settings"
                    level: 2
                }
                PlasmaComponents.ToolButton {
                    icon.name: "configure"
                    text: "All settings"
                    display: PlasmaComponents.AbstractButton.IconOnly
                    Accessible.name: "Open System Settings"
                    onClicked: root.launch("systemsettings")
                    PlasmaComponents.ToolTip.text: text
                    PlasmaComponents.ToolTip.visible: hovered
                }
            }

            GridLayout {
                Layout.fillWidth: true
                columns: 2
                rowSpacing: Tokens.spacing.small
                columnSpacing: Tokens.spacing.small

                Tile {
                    id: firstTile
                    iconName: root.dark ? "weather-clear-night" : "weather-clear"
                    title: "Dark mode"
                    detail: root.dark ? "AEGIS Dark" : "AEGIS Light"
                    toggle: true
                    checked: root.dark
                    onActivated: root.run(root.tool + " scheme " + (root.dark ? "light" : "dark"))
                }
                Tile {
                    iconName: "redshift-status-on"
                    title: "Night Light"
                    detail: root.facts.nightlight === "on" ? "Warmer colours" : "Off"
                    toggle: true
                    checked: root.facts.nightlight === "on"
                    onActivated: root.run(root.tool + " nightlight "
                                          + (root.facts.nightlight === "on" ? "off" : "on"))
                }
                Loader {
                    Layout.fillWidth: true
                    Layout.preferredHeight: Kirigami.Units.gridUnit * 3.4
                    source: "DndTile.qml"
                }
                Tile {
                    iconName: "spectacle"
                    title: "Screenshot"
                    detail: "Select an area"
                    onActivated: root.launch("spectacle --region")
                }
                Tile {
                    iconName: "network-wired"
                    title: "Network"
                    detail: "Connections"
                    onActivated: root.launch("systemsettings kcm_networkmanagement")
                }
                Tile {
                    iconName: "audio-volume-high"
                    title: "Sound"
                    detail: "Output and input"
                    onActivated: root.launch("systemsettings kcm_pulseaudio")
                }
                Tile {
                    iconName: "video-display"
                    title: "Display"
                    detail: "Size and scale"
                    onActivated: root.launch("systemsettings kcm_kscreen")
                }
                Tile {
                    iconName: "system-lock-screen"
                    title: "Lock"
                    detail: "Meta+L"
                    onActivated: root.launch("loginctl lock-session")
                }
            }

            PlasmaComponents.Label {
                text: "Liquid Glass"
                font.weight: Font.DemiBold
            }
            RowLayout {
                Layout.fillWidth: true
                spacing: Tokens.spacing.xs
                Repeater {
                    model: root.profiles
                    delegate: PlasmaComponents.Button {
                        required property var modelData
                        Layout.fillWidth: true
                        text: modelData.title
                        checkable: true
                        checked: (root.facts.glass || "auto") === modelData.id
                        Accessible.name: "Liquid Glass profile " + modelData.title
                        onClicked: root.run(root.tool + " glass " + modelData.id)
                    }
                }
            }
            PlasmaComponents.Label {
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                opacity: 0.65
                font.pointSize: Kirigami.Theme.smallFont.pointSize
                text: "Performance suits VirtualBox without 3D acceleration; Auto chooses for you."
            }
        }
        Component.onCompleted: firstTile.forceActiveFocus()
    }
}
