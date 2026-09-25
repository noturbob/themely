import Quickshell
import Quickshell.Wayland
import Quickshell.Widgets
import QtQuick

PanelWindow {
    id: win
    required property var themes
    signal picked(string slug, real x, real y)
    signal dismissed()
    signal openDashboard()

    readonly property int cardW: 240
    readonly property int cardH: 150
    property real shown: 0
    NumberAnimation on shown { from: 0; to: 1; duration: 280; easing.type: Easing.OutCubic }

    anchors { top: true; bottom: true; left: true; right: true }
    exclusionMode: ExclusionMode.Ignore
    color: "transparent"
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.namespace: "themely-switcher"
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.Exclusive

    // Card center in global (all-outputs) coordinates: where the reveal circle starts.
    function pick(item, slug) {
        const p = item.mapToItem(null, item.width / 2, item.cardCenterY ?? item.height / 2)
        win.picked(slug, p.x + win.screen.x, p.y + win.screen.y)
    }

    Rectangle {
        anchors.fill: parent
        color: Qt.rgba(0, 0, 0, 0.35 * win.shown)
        MouseArea { anchors.fill: parent; onClicked: win.dismissed() }
    }

    Rectangle {
        id: strip
        anchors.centerIn: parent
        anchors.verticalCenterOffset: (1 - win.shown) * 60
        opacity: win.shown
        width: Math.min(parent.width - 80, list.contentWidth + 32)
        height: win.cardH + 64
        radius: 28
        color: Qt.rgba(0.06, 0.06, 0.1, 0.78)
        border.color: Qt.rgba(1, 1, 1, 0.08)
        MouseArea { anchors.fill: parent }  // clicks on the strip don't close it

        ListView {
            id: list
            anchors.fill: parent
            anchors.margins: 16
            orientation: ListView.Horizontal
            spacing: 14
            clip: true
            focus: true
            keyNavigationWraps: true
            highlightMoveDuration: 200
            model: win.themes
            currentIndex: Math.max(0, win.themes.findIndex(t => t.current))

            Keys.onEscapePressed: win.dismissed()
            Keys.onReturnPressed: {
                const item = list.itemAtIndex(list.currentIndex)
                if (item) win.pick(item, win.themes[list.currentIndex].slug)
            }

            delegate: Item {
                id: card
                required property var modelData
                required property int index
                readonly property real cardCenterY: win.cardH / 2
                readonly property bool selected: ListView.isCurrentItem
                width: win.cardW
                height: win.cardH + 32
                scale: hover.hovered || selected ? 1.0 : 0.93
                Behavior on scale { NumberAnimation { duration: 200; easing.type: Easing.OutBack } }

                ClippingRectangle {
                    id: thumb
                    width: win.cardW
                    height: win.cardH
                    radius: 18
                    color: "black"
                    border.width: card.modelData.current ? 3 : (card.selected ? 2 : 0)
                    border.color: card.modelData.accent
                    Image {
                        anchors.fill: parent
                        source: "file://" + card.modelData.wallpaper
                        sourceSize.width: win.cardW * 2
                        fillMode: Image.PreserveAspectCrop
                        asynchronous: true
                        cache: false  // the path stays the same when a theme's wallpaper is edited
                    }
                }

                Row {
                    anchors.top: thumb.bottom
                    anchors.topMargin: 8
                    anchors.horizontalCenter: parent.horizontalCenter
                    spacing: 8
                    Rectangle {
                        width: 10; height: 10; radius: 5
                        anchors.verticalCenter: parent.verticalCenter
                        color: card.modelData.accent
                    }
                    Text { text: card.modelData.name; color: "white"; font.pixelSize: 14 }
                }

                HoverHandler { id: hover }
                TapHandler {
                    onTapped: { list.currentIndex = card.index; win.pick(card, card.modelData.slug) }
                }
            }

            footer: Item {
                width: 80
                height: win.cardH
                Rectangle {
                    anchors.centerIn: parent
                    width: 52; height: 52; radius: 26
                    color: gear.hovered ? Qt.rgba(1, 1, 1, 0.16) : Qt.rgba(1, 1, 1, 0.07)
                    Behavior on color { ColorAnimation { duration: 150 } }
                    Text { anchors.centerIn: parent; text: "+"; color: "white"; font.pixelSize: 26 }
                    HoverHandler { id: gear }
                    TapHandler { onTapped: win.openDashboard() }
                }
            }
        }
    }
}
