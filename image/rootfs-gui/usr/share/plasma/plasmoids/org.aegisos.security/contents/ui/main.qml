// AEGIS Security Dashboard v0 (GUI v1): a dock item whose popup shows the machine's
// security state. Read-only: the data comes from /usr/libexec/aegis/security-status,
// run as the desktop user through Plasma's executable data engine. Nothing here can
// change the system, and no part of it runs with elevated rights.
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

    readonly property string command: "/usr/libexec/aegis/security-status"
    property var facts: ({})
    property bool loaded: false

    readonly property bool healthy: facts.selinux === "Enforcing"
        && facts.root === "sealed-composefs" && facts.cmdline_check === "active"
    readonly property bool live: facts.live === "yes"
    readonly property string summary: !loaded ? "Checking…"
        : healthy ? "Protected: SELinux enforcing, sealed root"
        : live ? "Live session: SELinux " + (facts.selinux || "?") + ", root not sealed"
        : "Attention: see the AEGIS Security panel"

    Plasmoid.icon: "aegis-security"
    Plasmoid.status: healthy ? PlasmaCore.Types.PassiveStatus : PlasmaCore.Types.ActiveStatus
    toolTipMainText: "AEGIS Security"
    toolTipSubText: summary
    // In the dock: an icon with a popup. With room for it (a desktop widget, or the
    // window of 'plasmawindowed org.aegisos.security'): the dashboard itself.
    switchWidth: Kirigami.Units.gridUnit * 16
    switchHeight: Kirigami.Units.gridUnit * 16

    P5Support.DataSource {
        id: executable
        engine: "executable"
        connectedSources: []
        onNewData: (source, data) => {
            const parsed = {};
            for (const line of (data["stdout"] || "").split("\n")) {
                const at = line.indexOf("=");
                if (at > 0)
                    parsed[line.slice(0, at)] = line.slice(at + 1);
            }
            root.facts = parsed;
            root.loaded = true;
            disconnectSource(source);
        }
    }

    function refresh() {
        executable.connectSource(command);
    }

    Timer {
        interval: 60000
        running: true
        repeat: true
        triggeredOnStart: true
        onTriggered: root.refresh()
    }

    function stateOf(key) {
        const v = facts[key];
        if (!root.loaded || v === undefined || v === "unknown")
            return "unknown";
        switch (key) {
        case "selinux": return v === "Enforcing" ? "ok" : "critical";
        case "secureboot": return v === "enabled" ? "ok" : "warning";
        case "root": return v === "sealed-composefs" ? "ok" : v === "live-overlay" ? "warning" : "critical";
        case "cmdline_check": return v === "active" ? "ok" : v === "not-applicable-live" ? "warning" : "critical";
        case "firewall": return v === "active" ? "ok" : "warning";
        case "lockdown": return v === "none" ? "warning" : "ok";
        default: return "unknown";
        }
    }

    fullRepresentation: GlassSurface {
        Layout.minimumWidth: Kirigami.Units.gridUnit * 20
        Layout.minimumHeight: Kirigami.Units.gridUnit * 20
        Layout.preferredWidth: Kirigami.Units.gridUnit * 22
        Layout.preferredHeight: Kirigami.Units.gridUnit * 32
        material: "elevated"
        radius: Tokens.radius.large
        padding: Tokens.spacing.large

        ColumnLayout {
            anchors.fill: parent
            spacing: Tokens.spacing.medium

            RowLayout {
                spacing: Tokens.spacing.medium
                Kirigami.Icon {
                    source: "aegis-security"
                    Layout.preferredWidth: Kirigami.Units.iconSizes.large
                    Layout.preferredHeight: Kirigami.Units.iconSizes.large
                }
                ColumnLayout {
                    spacing: 0
                    Text {
                        text: "AEGIS Security"
                        color: Tokens.color.textPrimary
                        font.family: Tokens.type.family
                        font.pointSize: Tokens.type.title
                        font.weight: Tokens.type.weightStrong
                    }
                    Text {
                        text: root.summary
                        color: root.healthy ? Tokens.color.ok : Tokens.color.warning
                        font.family: Tokens.type.family
                        font.pointSize: Tokens.type.caption
                    }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                height: 1
                color: Qt.rgba(0.62, 0.95, 1.0, 0.18)
            }

            PlasmaComponents.ScrollView {
                id: rows
                Layout.fillWidth: true
                Layout.fillHeight: true
                contentWidth: availableWidth

                ColumnLayout {
                    width: rows.availableWidth
                    spacing: Tokens.spacing.medium

            StatusRow { Layout.fillWidth: true; label: "SELinux"; value: root.facts.selinux || "…"; state: root.stateOf("selinux") }
            StatusRow {
                Layout.fillWidth: true
                label: "Secure Boot"
                value: root.facts.secureboot || "…"
                state: root.stateOf("secureboot")
                detail: root.facts.secureboot === "disabled"
                    ? "This firmware does not verify the boot chain" : ""
            }
            StatusRow {
                Layout.fillWidth: true
                label: "Root filesystem"
                value: root.facts.root === "sealed-composefs" ? "Sealed (composefs, fs-verity)"
                    : root.facts.root === "live-overlay" ? "Live: read-only image + RAM overlay (not sealed)"
                    : (root.facts.root || "…")
                state: root.stateOf("root")
                detail: root.facts.root_digest && root.facts.root_digest !== "none"
                    ? "digest " + root.facts.root_digest.slice(0, 24) + "…" : ""
            }
            StatusRow { Layout.fillWidth: true; label: "Kernel command line check"; value: root.facts.cmdline_check === "not-applicable-live" ? "Not used in the live session" : (root.facts.cmdline_check || "…"); state: root.stateOf("cmdline_check") }
            StatusRow { Layout.fillWidth: true; label: "Firewall"; value: root.facts.firewall || "…"; state: root.stateOf("firewall") }
            StatusRow { Layout.fillWidth: true; label: "Kernel lockdown"; value: root.facts.lockdown || "…"; state: root.stateOf("lockdown") }
            StatusRow { Layout.fillWidth: true; label: "Running deployment"; value: root.facts.deployment || "…"; state: "unknown" }
            StatusRow { Layout.fillWidth: true; label: "Updates"; value: root.facts.updates === "not-applicable-live" ? "None in a live session" : (root.facts.updates || "…"); state: "unknown" }
                }
            }

            RowLayout {
                Layout.fillWidth: true
                Text {
                    Layout.fillWidth: true
                    text: "Read-only · checked " + (root.facts.checked || "–")
                    color: Tokens.color.textSecondary
                    font.family: Tokens.type.family
                    font.pointSize: Tokens.type.caption
                    elide: Text.ElideRight
                }
                PlasmaComponents.ToolButton {
                    icon.name: "view-refresh"
                    text: "Refresh"
                    onClicked: root.refresh()
                }
            }
        }
    }
}
