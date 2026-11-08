import QtQuick

// Large digital clock with a small date beneath it.
// Each minute change eases in softly instead of snapping.
Item {
    id: clock

    property bool use24h: true
    property string fontFamily: ""
    property real unit: 1
    property date now: new Date()

    readonly property string timeString: Qt.formatTime(now, use24h ? "H:mm" : "h:mm")
    readonly property string dateString: Qt.formatDate(now, "dddd, d MMMM")

    implicitWidth: Math.max(timeText.implicitWidth, dateText.implicitWidth)
    implicitHeight: timeText.implicitHeight + dateText.implicitHeight + 6 * unit

    Timer {
        interval: 1000
        running: true
        repeat: true
        onTriggered: clock.now = new Date()
    }

    Text {
        id: timeText
        anchors.horizontalCenter: parent.horizontalCenter
        text: clock.timeString
        color: "#F2F2F2"
        font.family: clock.fontFamily
        font.pixelSize: 150 * clock.unit
        font.weight: Font.DemiBold
        font.letterSpacing: -4 * clock.unit
        renderType: Text.QtRendering

        onTextChanged: minuteTick.restart()
        ParallelAnimation {
            id: minuteTick
            NumberAnimation { target: timeText; property: "opacity"; from: 0.35; to: 1; duration: 700; easing.type: Easing.OutCubic }
            NumberAnimation { target: timeText; property: "y"; from: 7 * clock.unit; to: 0; duration: 700; easing.type: Easing.OutCubic }
        }
    }

    Text {
        id: dateText
        anchors.horizontalCenter: parent.horizontalCenter
        y: timeText.implicitHeight - 6 * clock.unit
        text: clock.dateString
        color: Qt.rgba(1, 1, 1, 0.58)
        font.family: clock.fontFamily
        font.pixelSize: 21 * clock.unit
        font.weight: Font.Medium
        renderType: Text.QtRendering
    }
}
