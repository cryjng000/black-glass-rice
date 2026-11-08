import QtQuick
import QtQuick.Effects

// A frosted, translucent black glass surface.
// It samples the (already blurred) wallpaper behind it, blurs and darkens it again,
// then layers tint, sheen, a hairline border and a soft shadow on top.
Item {
    id: glass

    property Item backdrop: null      // the blurred wallpaper item to sample
    property bool fx: true            // false = flat translucent fallback (no shaders)
    property real radius: 30
    property real pad: 40             // extra sampled margin so blur edges stay clean
    property real tint: 0.40
    property real shadowStrength: 0.65
    property real shadowOffset: 26

    default property alias content: contentItem.data

    function refresh() {
        if (!backdrop || !fx || width <= 0 || height <= 0)
            return
        var p = glass.mapToItem(backdrop, 0, 0)
        frostSource.sourceRect = Qt.rect(p.x - pad, p.y - pad, width + pad * 2, height + pad * 2)
    }
    function scheduleRefresh() { refreshTimer.restart() }

    Timer { id: refreshTimer; interval: 30; onTriggered: glass.refresh() }
    onXChanged: scheduleRefresh()
    onYChanged: scheduleRefresh()
    onWidthChanged: scheduleRefresh()
    onHeightChanged: scheduleRefresh()
    onBackdropChanged: scheduleRefresh()
    Component.onCompleted: scheduleRefresh()

    Connections {
        target: glass.backdrop
        ignoreUnknownSignals: true
        function onWidthChanged() { glass.scheduleRefresh() }
        function onHeightChanged() { glass.scheduleRefresh() }
    }
    Connections {
        target: glass.parent
        ignoreUnknownSignals: true
        function onWidthChanged() { glass.scheduleRefresh() }
        function onHeightChanged() { glass.scheduleRefresh() }
    }

    // ---- soft drop shadow (the opaque frost layer below hides the shape itself) ----
    Rectangle {
        id: shadowShape
        anchors.fill: parent
        radius: glass.radius
        color: "#000000"
        visible: false
    }
    MultiEffect {
        anchors.fill: shadowShape
        source: shadowShape
        autoPaddingEnabled: true
        blurMax: 64
        shadowEnabled: true
        shadowColor: "#000000"
        shadowOpacity: glass.shadowStrength
        shadowBlur: 1.0
        shadowVerticalOffset: glass.shadowOffset
    }

    // ---- frosted backdrop ----
    ShaderEffectSource {
        id: frostSource
        visible: false
        sourceItem: glass.fx ? glass.backdrop : null
        live: true
        width: glass.width + glass.pad * 2
        height: glass.height + glass.pad * 2
    }
    Item {
        id: maskItem
        visible: false
        layer.enabled: true
        width: glass.width + glass.pad * 2
        height: glass.height + glass.pad * 2
        Rectangle {
            x: glass.pad
            y: glass.pad
            width: glass.width
            height: glass.height
            radius: glass.radius
            color: "#000000"
        }
    }
    MultiEffect {
        visible: glass.fx
        x: -glass.pad
        y: -glass.pad
        width: glass.width + glass.pad * 2
        height: glass.height + glass.pad * 2
        source: frostSource
        autoPaddingEnabled: false
        blurEnabled: true
        blur: 1.0
        blurMax: 48
        brightness: -0.22
        saturation: -1.0
        maskEnabled: true
        maskSource: maskItem
    }

    // flat fallback when shaders are unavailable
    Rectangle {
        visible: !glass.fx
        anchors.fill: parent
        radius: glass.radius
        color: "#121212"
        opacity: 0.9
    }

    // ---- translucent black tint ----
    Rectangle {
        anchors.fill: parent
        radius: glass.radius
        color: Qt.rgba(0.04, 0.04, 0.04, glass.tint)
    }

    // ---- sheen: light diffusing from the top edge ----
    Rectangle {
        anchors.fill: parent
        radius: glass.radius
        gradient: Gradient {
            GradientStop { position: 0.0; color: Qt.rgba(1, 1, 1, 0.10) }
            GradientStop { position: 0.45; color: Qt.rgba(1, 1, 1, 0.025) }
            GradientStop { position: 1.0; color: Qt.rgba(1, 1, 1, 0.0) }
        }
    }

    // ---- hairline border ----
    Rectangle {
        anchors.fill: parent
        radius: glass.radius
        color: "transparent"
        border.width: 1
        border.color: Qt.rgba(1, 1, 1, 0.09)
    }

    // ---- specular highlight along the top edge ----
    Rectangle {
        y: 0
        x: glass.radius * 0.9
        width: glass.width - glass.radius * 1.8
        height: 1
        gradient: Gradient {
            orientation: Gradient.Horizontal
            GradientStop { position: 0.0; color: Qt.rgba(1, 1, 1, 0.0) }
            GradientStop { position: 0.5; color: Qt.rgba(1, 1, 1, 0.30) }
            GradientStop { position: 1.0; color: Qt.rgba(1, 1, 1, 0.0) }
        }
    }

    Item { id: contentItem; anchors.fill: parent }
}
