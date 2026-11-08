import QtQuick

// Minimal pill-shaped input with hover and focus transitions.
Item {
    id: field

    property real unit: 1
    property string fontFamily: ""
    property string placeholder: ""
    property bool secret: false
    property Item nextItem: null
    property alias text: input.text
    property alias input: input

    signal accepted()
    signal edited()       // user typed (not programmatic changes)

    readonly property int dur: 240
    readonly property bool hovered: hover.hovered
    readonly property bool focused: input.activeFocus

    implicitWidth: 280 * unit
    implicitHeight: 46 * unit

    // soft focus halo
    Rectangle {
        anchors.fill: parent
        anchors.margins: -4 * field.unit
        radius: height / 2
        color: "transparent"
        border.width: 4 * field.unit
        border.color: Qt.rgba(1, 1, 1, 0.06)
        opacity: field.focused ? 1 : 0
        scale: field.focused ? 1 : 0.97
        Behavior on opacity { NumberAnimation { duration: field.dur; easing.type: Easing.OutCubic } }
        Behavior on scale { NumberAnimation { duration: field.dur; easing.type: Easing.OutCubic } }
    }

    Rectangle {
        id: bg
        anchors.fill: parent
        radius: height / 2
        color: field.focused ? Qt.rgba(1, 1, 1, 0.10)
             : field.hovered ? Qt.rgba(1, 1, 1, 0.075)
             : Qt.rgba(1, 1, 1, 0.052)
        border.width: 1
        border.color: field.focused ? Qt.rgba(1, 1, 1, 0.24) : Qt.rgba(1, 1, 1, 0.07)
        Behavior on color { ColorAnimation { duration: field.dur; easing.type: Easing.OutCubic } }
        Behavior on border.color { ColorAnimation { duration: field.dur; easing.type: Easing.OutCubic } }
    }

    Text {
        anchors.left: parent.left
        anchors.leftMargin: 20 * field.unit
        anchors.verticalCenter: parent.verticalCenter
        text: field.placeholder
        color: "#888888"
        font.family: field.fontFamily
        font.pixelSize: 16 * field.unit
        opacity: input.text.length === 0 ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: 160; easing.type: Easing.OutCubic } }
    }

    TextInput {
        id: input
        anchors.fill: parent
        anchors.leftMargin: 20 * field.unit
        anchors.rightMargin: 20 * field.unit
        verticalAlignment: TextInput.AlignVCenter
        color: "#F2F2F2"
        selectionColor: Qt.rgba(1, 1, 1, 0.28)
        selectedTextColor: "#FFFFFF"
        font.family: field.fontFamily
        font.pixelSize: 16 * field.unit
        echoMode: field.secret ? TextInput.Password : TextInput.Normal
        passwordCharacter: "\u2022"
        selectByMouse: true
        clip: true
        autoScroll: true
        inputMethodHints: Qt.ImhNoPredictiveText | Qt.ImhNoAutoUppercase
        KeyNavigation.tab: field.nextItem
        onAccepted: field.accepted()
        onTextEdited: field.edited()
    }

    HoverHandler { id: hover; cursorShape: Qt.IBeamCursor }
    TapHandler { onTapped: input.forceActiveFocus() }
}
