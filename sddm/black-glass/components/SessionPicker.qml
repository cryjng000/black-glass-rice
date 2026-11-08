import QtQuick
import QtQuick.Shapes

// Compact session selector (e.g. "Hyprland") that opens a small glass menu upwards.
Item {
    id: picker

    property var sessions: null       // SDDM sessionModel
    property int currentIndex: 0
    property string currentName: ""
    property Item backdrop: null
    property bool fx: true
    property real unit: 1
    property string fontFamily: ""
    property bool open: false

    signal selected(int index)

    readonly property int dur: 240

    implicitWidth: trigger.width
    implicitHeight: trigger.height

    function refreshName() {
        var it = rep.itemAt(currentIndex)
        currentName = it ? it.label : ""
    }
    onCurrentIndexChanged: refreshName()
    Component.onCompleted: refreshName()

    // ---- trigger ----
    Rectangle {
        id: trigger
        width: row.implicitWidth + 30 * picker.unit
        height: 38 * picker.unit
        radius: height / 2
        color: picker.open ? Qt.rgba(1, 1, 1, 0.14)
             : hover.hovered ? Qt.rgba(1, 1, 1, 0.09)
             : Qt.rgba(1, 1, 1, 0.0)
        border.width: picker.activeFocus ? 2 : 0
        border.color: Qt.rgba(1, 1, 1, 0.5)
        Behavior on color { ColorAnimation { duration: picker.dur; easing.type: Easing.OutCubic } }

        Row {
            id: row
            anchors.centerIn: parent
            spacing: 8 * picker.unit
            Text {
                anchors.verticalCenter: parent.verticalCenter
                text: picker.currentName !== "" ? picker.currentName : "Session"
                color: (hover.hovered || picker.open) ? "#F2F2F2" : "#9A9A9A"
                font.family: picker.fontFamily
                font.pixelSize: 14 * picker.unit
                font.weight: Font.Medium
                Behavior on color { ColorAnimation { duration: picker.dur; easing.type: Easing.OutCubic } }
            }
            Shape {
                width: 12
                height: 12
                anchors.verticalCenter: parent.verticalCenter
                scale: (10 * picker.unit) / 12
                rotation: picker.open ? 180 : 0
                Behavior on rotation { NumberAnimation { duration: picker.dur; easing.type: Easing.OutCubic } }
                layer.enabled: true
                layer.samples: 4
                layer.textureSize: Qt.size(48, 48)
                ShapePath {
                    strokeColor: (hover.hovered || picker.open) ? "#F2F2F2" : "#9A9A9A"
                    strokeWidth: 1.6
                    fillColor: "transparent"
                    capStyle: ShapePath.RoundCap
                    joinStyle: ShapePath.RoundJoin
                    PathSvg { path: "M2.5 4.5 L6 8 L9.5 4.5" }
                }
            }
        }
        HoverHandler { id: hover; cursorShape: Qt.PointingHandCursor }
        TapHandler { onTapped: picker.open = !picker.open }
    }
    activeFocusOnTab: true
    Keys.onReturnPressed: picker.open = !picker.open
    Keys.onSpacePressed: picker.open = !picker.open

    // ---- menu ----
    GlassPanel {
        id: popup
        backdrop: picker.backdrop
        fx: picker.fx
        radius: 20 * picker.unit
        pad: 24
        tint: 0.5
        shadowOffset: 14
        width: 240 * picker.unit
        height: list.implicitHeight + 16 * picker.unit
        anchors.left: trigger.left
        anchors.bottom: trigger.top
        anchors.bottomMargin: (picker.open ? 10 : 2) * picker.unit
        opacity: picker.open ? 1 : 0
        visible: opacity > 0.01
        Behavior on opacity { NumberAnimation { duration: picker.dur; easing.type: Easing.OutCubic } }
        Behavior on anchors.bottomMargin { NumberAnimation { duration: picker.dur; easing.type: Easing.OutCubic } }

        Column {
            id: list
            x: 8 * picker.unit
            y: 8 * picker.unit
            width: parent.width - 16 * picker.unit
            Repeater {
                id: rep
                model: picker.sessions
                onItemAdded: picker.refreshName()
                delegate: Item {
                    id: entry
                    property string label: model.name
                    readonly property bool current: index === picker.currentIndex
                    width: list.width
                    height: 38 * picker.unit

                    Rectangle {
                        anchors.fill: parent
                        radius: 14 * picker.unit
                        color: rowHover.hovered ? Qt.rgba(1, 1, 1, 0.10) : "transparent"
                        Behavior on color { ColorAnimation { duration: 160; easing.type: Easing.OutCubic } }
                    }
                    Text {
                        anchors.left: parent.left
                        anchors.leftMargin: 14 * picker.unit
                        anchors.right: parent.right
                        anchors.rightMargin: 36 * picker.unit
                        anchors.verticalCenter: parent.verticalCenter
                        text: entry.label
                        elide: Text.ElideRight
                        color: entry.current ? "#F2F2F2" : "#B4B4B4"
                        font.family: picker.fontFamily
                        font.pixelSize: 14 * picker.unit
                        font.weight: entry.current ? Font.Medium : Font.Normal
                    }
                    Rectangle {
                        anchors.right: parent.right
                        anchors.rightMargin: 16 * picker.unit
                        anchors.verticalCenter: parent.verticalCenter
                        width: 6 * picker.unit
                        height: width
                        radius: width / 2
                        color: "#F2F2F2"
                        opacity: entry.current ? 1 : 0
                        Behavior on opacity { NumberAnimation { duration: 160; easing.type: Easing.OutCubic } }
                    }
                    HoverHandler { id: rowHover; cursorShape: Qt.PointingHandCursor }
                    TapHandler {
                        onTapped: {
                            picker.currentIndex = index
                            picker.selected(index)
                            picker.open = false
                        }
                    }
                }
            }
        }
    }
}
