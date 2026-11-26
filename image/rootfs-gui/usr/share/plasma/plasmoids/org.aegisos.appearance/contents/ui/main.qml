// AEGIS Appearance (GUI v2): choose the Liquid Glass rendering profile. It runs
// /usr/libexec/aegis/glass-profile as the desktop user, which changes only the user's own
// KDE settings. Opened from the launcher ("AEGIS Appearance") as a window.
import QtQuick
import QtQuick.Layouts
import org.kde.plasma.plasmoid
import org.kde.plasma.components as PlasmaComponents
import org.kde.plasma.plasma5support as P5Support
import org.kde.kirigami as Kirigami
import org.aegisos.style

PlasmoidItem {
    id: root

    readonly property string tool: "/usr/libexec/aegis/glass-profile"
    property var facts: ({})
    property bool busy: false

    switchWidth: Kirigami.Units.gridUnit * 16
    switchHeight: Kirigami.Units.gridUnit * 16
    Plasmoid.icon: "preferences-desktop-theme-global"

    readonly property var profiles: [
        { id: "auto", title: "Automatic",
          text: "Balanced Glass when the graphics card renders, Performance Glass with software rendering." },
        { id: "full", title: "Full Liquid Glass",
          text: "Strong backdrop blur with grain, full-length animations. For hardware-accelerated graphics." },
        { id: "balanced", title: "Balanced Glass",
          text: "Lighter blur and shorter animations: the AEGIS look at a lower cost." },
        { id: "performance", title: "Performance Glass",
          text: "No backdrop blur, more opaque surfaces, short animations. For VirtualBox without 3D or weak GPUs." }
    ]

    P5Support.DataSource {
        id: executable
        engine: "executable"
        connectedSources: []
        onNewData: (source, data) => {
            const parsed = {};
            for (const line of (data["stdout"] || "").split(/[\n ]/)) {
                const at = line.indexOf("=");
                if (at > 0)
                    parsed[line.slice(0, at)] = line.slice(at + 1);
            }
            if (source.indexOf(" status") > 0)
                root.facts = parsed;
            else
                executable.connectSource(root.tool + " status");
            root.busy = false;
            disconnectSource(source);
        }
    }

    function choose(profile) {
        busy = true;
        executable.connectSource(tool + " apply " + profile);
    }

    Component.onCompleted: executable.connectSource(tool + " status")

    fullRepresentation: GlassSurface {
        Layout.minimumWidth: Kirigami.Units.gridUnit * 22
        Layout.preferredWidth: Kirigami.Units.gridUnit * 26
        Layout.preferredHeight: Kirigami.Units.gridUnit * 30
        material: "elevated"
        radius: Tokens.radius.large
        padding: Tokens.spacing.large

        ColumnLayout {
            anchors.fill: parent
            spacing: Tokens.spacing.medium

            Kirigami.Heading {
                text: "AEGIS Appearance"
                level: 2
            }
            PlasmaComponents.Label {
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                opacity: 0.8
                text: "Renderer: " + (root.facts.renderer || "…") + "\nIn use: "
                    + (root.facts.effective || "…") + (root.facts.choice === "auto" ? " (automatic)" : "")
            }

            Repeater {
                model: root.profiles
                delegate: GlassSurface {
                    id: card
                    required property var modelData
                    readonly property bool selected: root.facts.choice === modelData.id
                    Layout.fillWidth: true
                    Layout.preferredHeight: Kirigami.Units.gridUnit * 3.6
                    material: "control"
                    radius: Tokens.radius.medium
                    hovered: area.containsMouse
                    pressed: area.pressed || selected

                    ColumnLayout {
                        anchors.fill: parent
                        spacing: 2
                        PlasmaComponents.Label {
                            text: (card.selected ? "● " : "○ ") + card.modelData.title
                            font.weight: Font.DemiBold
                        }
                        PlasmaComponents.Label {
                            Layout.fillWidth: true
                            wrapMode: Text.WordWrap
                            opacity: 0.75
                            font.pointSize: Kirigami.Theme.smallFont.pointSize
                            text: card.modelData.text
                        }
                    }
                    MouseArea {
                        id: area
                        anchors.fill: parent
                        hoverEnabled: true
                        enabled: !root.busy
                        onClicked: root.choose(card.modelData.id)
                    }
                }
            }
            PlasmaComponents.Label {
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                opacity: 0.6
                font.pointSize: Kirigami.Theme.smallFont.pointSize
                text: "The glass is backdrop blur and drawn highlights; it does not refract light."
            }
        }
    }
}
