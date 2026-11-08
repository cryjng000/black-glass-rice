import QtQuick
import QtQuick.Effects
import QtQuick.Shapes

// Circular user avatar: the user's face icon if readable, otherwise a monogram
// (or a neutral silhouette while no username is entered).
Item {
    id: avatar

    property string name: ""
    property string icon: ""
    property string fontFamily: ""
    property real size: 92

    width: size
    height: size

    readonly property bool hasImage: img.status === Image.Ready

    Rectangle {
        anchors.fill: parent
        radius: width / 2
        gradient: Gradient {
            GradientStop { position: 0.0; color: "#3a3a3a" }
            GradientStop { position: 1.0; color: "#171717" }
        }
        border.width: 1
        border.color: Qt.rgba(1, 1, 1, 0.14)
    }

    // silhouette
    Shape {
        id: silhouette
        width: 24
        height: 24
        anchors.centerIn: parent
        scale: (avatar.size * 0.62) / 24
        opacity: (avatar.name === "" && !avatar.hasImage) ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: 240; easing.type: Easing.OutCubic } }
        layer.enabled: true
        layer.samples: 4
        layer.textureSize: Qt.size(192, 192)
        ShapePath {
            strokeColor: "transparent"
            fillColor: Qt.rgba(1, 1, 1, 0.5)
            PathSvg { path: "M8 8 A4 4 0 1 0 16 8 A4 4 0 1 0 8 8 Z" }
            PathSvg { path: "M4 22 C4 17 8 14.5 12 14.5 C16 14.5 20 17 20 22 Z" }
        }
    }

    // monogram
    Text {
        anchors.centerIn: parent
        text: avatar.name.length > 0 ? avatar.name.charAt(0).toUpperCase() : ""
        color: Qt.rgba(1, 1, 1, 0.82)
        font.family: avatar.fontFamily
        font.pixelSize: avatar.size * 0.42
        font.weight: Font.Medium
        opacity: (avatar.name !== "" && !avatar.hasImage) ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: 240; easing.type: Easing.OutCubic } }
    }

    // photo
    Image {
        id: img
        anchors.fill: parent
        source: avatar.icon
        fillMode: Image.PreserveAspectCrop
        asynchronous: true
        mipmap: true
        visible: false
        sourceSize.width: avatar.size * 2
        sourceSize.height: avatar.size * 2
    }
    Item {
        id: photoMask
        anchors.fill: parent
        visible: false
        layer.enabled: true
        Rectangle { anchors.fill: parent; radius: width / 2; color: "#000000" }
    }
    MultiEffect {
        anchors.fill: parent
        source: img
        visible: avatar.hasImage
        maskEnabled: true
        maskSource: photoMask
    }
}
