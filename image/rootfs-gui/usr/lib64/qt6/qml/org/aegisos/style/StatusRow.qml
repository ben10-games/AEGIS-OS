// One labelled status line: a state dot plus text, so state is never shown by colour
// alone. state: "ok" | "warning" | "critical" | "unknown".
import QtQuick
import QtQuick.Layouts

RowLayout {
    id: row

    property string label
    property string value
    property string state: "unknown"
    property string detail: ""

    spacing: Tokens.spacing.small

    Rectangle {
        Layout.alignment: Qt.AlignTop
        Layout.topMargin: 5
        width: 10
        height: 10
        radius: 5
        color: row.state === "ok" ? Tokens.color.ok
             : row.state === "warning" ? Tokens.color.warning
             : row.state === "critical" ? Tokens.color.critical : Tokens.color.unknown
    }
    ColumnLayout {
        Layout.fillWidth: true
        spacing: 1
        Text {
            text: row.label
            color: Tokens.color.textSecondary
            font.family: Tokens.type.family
            font.pointSize: Tokens.type.caption
        }
        Text {
            Layout.fillWidth: true
            text: row.value
            color: Tokens.color.textPrimary
            font.family: Tokens.type.family
            font.pointSize: Tokens.type.body
            font.weight: Tokens.type.weightStrong
            wrapMode: Text.Wrap
        }
        Text {
            Layout.fillWidth: true
            visible: row.detail.length > 0
            text: row.detail
            color: Tokens.color.textSecondary
            font.family: Tokens.type.family
            font.pointSize: Tokens.type.caption
            elide: Text.ElideMiddle
        }
    }
}
