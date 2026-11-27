// Scene 6, Security and privacy: how AEGIS protects this computer, from the machine's
// real state (read-only, from the Security Dashboard's helper). Each card turns over to
// a plain explanation (click, or Tab and Enter). Honest about what is off: with Secure
// Boot off the card says what that means.
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import AegisWelcome

Item {
    id: scene
    readonly property var facts: welcome.securityFacts()
    property var opened: []

    function open(id) {
        if (opened.indexOf(id) < 0)
            opened = opened.concat([id]);
        if (opened.length >= 3)
            welcome.complete("security.explore");
    }

    readonly property var cards: [
        { id: "sealed", title: "Sealed system",
          state: facts.root === "sealed-composefs" ? "On" : (facts.root || "unknown"),
          good: facts.root === "sealed-composefs",
          text: "The operating system is a read-only, sealed image. Every system file is checked "
              + "when it is read; a changed file cannot be read at all. Your files live apart from it." },
        { id: "selinux", title: "SELinux",
          state: facts.selinux || "unknown", good: facts.selinux === "Enforcing",
          text: "Every program is limited to what it needs. Even a program with a flaw cannot "
              + "reach what its rules do not allow." },
        { id: "secureboot", title: "Secure Boot",
          state: facts.secureboot || "unknown", good: facts.secureboot === "enabled",
          text: facts.secureboot === "enabled"
              ? "The firmware starts only AEGIS-signed start-up files."
              : "Off here (as in VirtualBox by default): the firmware does not check the start-up "
                + "files, so someone who can change this computer's disk file could replace them. "
                + "The sealed system checks still run." },
        { id: "updates", title: "Signed updates",
          state: "Required", good: true,
          text: "System updates are accepted only with AEGIS's signature. An update can be rolled "
              + "back; your files, settings and apps are kept either way." },
        { id: "firewall", title: "Firewall",
          state: facts.firewall || "unknown", good: (facts.firewall || "").length > 0,
          text: "Nothing from outside can connect to this computer unless you allow it. There "
              + "is no remote login." },
        { id: "apps", title: "App permissions",
          state: "Per app", good: true,
          text: "Apps from the App Center run in a sandbox and see only what their permissions "
              + "allow. The App Center shows them before you install." }
    ]

    ColumnLayout {
        anchors.fill: parent
        spacing: 12
        Step {
            key: "security.explore"
            title: "Turn over three cards"
            hint: "Click a card, or Tab to it and press Enter."
        }
        GridLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            columns: 3
            rowSpacing: 12
            columnSpacing: 12
            Repeater {
                model: scene.cards
                delegate: Item {
                    id: card
                    required property var modelData
                    property bool flipped: false
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    activeFocusOnTab: true
                    Accessible.role: Accessible.Button
                    Accessible.name: modelData.title + ": " + modelData.state
                    Accessible.description: modelData.text
                    Accessible.onPressAction: turn()
                    function turn() { flipped = !flipped; scene.open(modelData.id); }
                    Keys.onReturnPressed: turn()
                    Keys.onSpacePressed: turn()

                    Glass {
                        anchors.fill: parent
                        radius: 16
                        tint: card.flipped ? 0.85 : 0.65
                        Rectangle {
                            anchors.fill: parent
                            radius: 16
                            color: "transparent"
                            border.width: card.activeFocus ? 2 : 0
                            border.color: "#4fd1e8"
                        }
                        ColumnLayout {
                            anchors { fill: parent; margins: 14 }
                            visible: !card.flipped
                            Label { text: card.modelData.title; color: "#eef6fb"; font { family: "Inter"; pixelSize: 16; weight: Font.DemiBold } }
                            Label {
                                text: card.modelData.state
                                color: card.modelData.good ? "#5fd39a" : "#f2c46d"
                                font { family: "Inter"; pixelSize: 14 }
                            }
                            Item { Layout.fillHeight: true }
                            Label { text: "Why it matters →"; color: "#a9b8c6"; font { family: "Inter"; pixelSize: 12 } }
                        }
                        Label {
                            anchors { fill: parent; margins: 14 }
                            visible: card.flipped
                            text: card.modelData.text
                            wrapMode: Text.WordWrap
                            color: "#eef6fb"
                            font { family: "Inter"; pixelSize: 13 }
                        }
                    }
                    MouseArea { anchors.fill: parent; onClicked: card.turn() }
                }
            }
        }
    }
}
