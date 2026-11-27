// AEGIS App Center (v3, M12): Discover (search and categories), Installed and Updates.
// A status line shows what is happening (with progress) and errors in plain words, with
// a way to try again. Installs are for the user's account only.
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import AegisAppCenter

ApplicationWindow {
    id: window
    visible: true
    width: 1100
    height: 740
    minimumWidth: 720
    minimumHeight: 520
    title: "AEGIS App Center"
    color: "#0b1220"

    property string query: ""
    property string category: ""
    property int tab: 0       // 0 Discover, 1 Installed, 2 Updates
    property var open: null   // the app whose page is shown
    property var lastAction: null

    readonly property var results: {
        center.catalogueSize; center.installedIds;  // re-evaluate when these change
        if (tab === 1)
            return center.installedIds.map(id => center.details(id)).filter(a => a.id);
        if (tab === 2)
            return center.updateIds.map(id => center.details(id)).filter(a => a.id);
        return center.search(query, category);
    }

    header: Rectangle {
        height: 64
        color: Qt.rgba(0.07, 0.11, 0.18, 0.96)
        RowLayout {
            anchors { fill: parent; leftMargin: 20; rightMargin: 20 }
            spacing: 14
            Label {
                text: "App Center"
                color: "#eef6fb"
                font { family: "Inter"; pixelSize: 20; weight: Font.DemiBold }
            }
            Repeater {
                model: ["Discover", "Installed", "Updates"]
                delegate: Button {
                    required property string modelData
                    required property int index
                    text: index === 2 && center.updateIds.length > 0
                        ? modelData + " (" + center.updateIds.length + ")" : modelData
                    checkable: true
                    checked: window.tab === index
                    Accessible.name: modelData
                    onClicked: { window.tab = index; window.open = null; }
                }
            }
            TextField {
                id: search
                Layout.fillWidth: true
                placeholderText: "Search applications"
                Accessible.name: "Search applications"
                font.family: "Inter"
                onTextChanged: { window.query = text; window.tab = 0; window.open = null; }
            }
            Button {
                text: "Update all"
                visible: window.tab === 2 && center.updateIds.length > 0
                enabled: !center.busy
                Accessible.name: "Update all applications"
                onClicked: center.update("")
            }
        }
    }

    footer: Rectangle {
        height: visible ? 44 : 0
        visible: center.busy || center.error.length > 0 || center.status === "Done"
        color: center.error.length > 0 ? Qt.rgba(0.5, 0.15, 0.17, 0.95) : Qt.rgba(0.07, 0.11, 0.18, 0.96)
        RowLayout {
            anchors { fill: parent; leftMargin: 20; rightMargin: 20 }
            spacing: 12
            Label {
                Layout.fillWidth: true
                text: center.error.length > 0 ? center.error
                    : center.status + (center.busy && center.progress > 0 ? "  " + center.progress + " %" : "")
                color: "#eef6fb"
                elide: Text.ElideRight
                font.family: "Inter"
                Accessible.role: Accessible.StatusBar
                Accessible.name: text
            }
            ProgressBar {
                visible: center.busy
                Layout.preferredWidth: 240
                from: 0; to: 100
                value: center.progress
                indeterminate: center.progress === 0
            }
            Button {
                visible: center.error.length > 0
                text: "Try again"
                onClicked: center.refresh()
            }
        }
    }

    StackLayout {
        anchors.fill: parent
        currentIndex: window.open ? 1 : 0

        ColumnLayout {
            spacing: 12
            Flow {
                Layout.fillWidth: true
                Layout.margins: 20
                Layout.bottomMargin: 0
                spacing: 8
                visible: window.tab === 0
                Button {
                    text: "All"
                    checkable: true
                    checked: window.category === ""
                    onClicked: window.category = ""
                }
                Repeater {
                    model: center.categories()
                    delegate: Button {
                        required property var modelData
                        text: modelData.title
                        checkable: true
                        checked: window.category === modelData.id
                        Accessible.name: "Category " + modelData.title
                        onClicked: window.category = modelData.id
                    }
                }
            }
            Label {
                Layout.margins: 20
                visible: window.results.length === 0
                color: "#a9b8c6"
                font { family: "Inter"; pixelSize: 15 }
                text: window.tab === 2 ? "Everything is up to date."
                    : window.tab === 1 ? "No applications installed yet."
                    : center.catalogueSize === 0 ? "Loading the catalogue from Flathub…"
                    : "Nothing matches your search."
            }
            GridView {
                id: grid
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.margins: 20
                clip: true
                cellWidth: Math.max(300, width / Math.max(1, Math.floor(width / 320)))
                cellHeight: 108
                model: window.results
                keyNavigationEnabled: true
                ScrollBar.vertical: ScrollBar {}
                delegate: Item {
                    required property var modelData
                    width: grid.cellWidth
                    height: grid.cellHeight
                    AppCard {
                        anchors { fill: parent; margins: 6 }
                        app: parent.modelData
                        onOpen: window.open = parent.modelData
                    }
                }
            }
        }

        Loader {
            active: window.open !== null
            sourceComponent: Details {
                app: window.open
                onBack: window.open = null
            }
        }
    }

    Shortcut {
        sequences: [StandardKey.Find]
        onActivated: search.forceActiveFocus()
    }
    Shortcut {
        sequences: [StandardKey.Back, "Escape"]
        onActivated: window.open = null
    }
    Component.onCompleted: search.forceActiveFocus()
}
