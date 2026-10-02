import Quickshell
import Quickshell.Wayland
import QtQuick
import QtQuick.Effects

// A blurred, half-dimmed wallpaper that niri moves into the overview backdrop (layer-rule on its namespace),
// so only Mod+Tab shows it; the desktop keeps swaybg's plain wallpaper.
Scope {
    id: backdrop
    property int version: 0  // the wallpaper path never changes across themes, so bump to re-read it
    function reload() { version++ }

    Variants {
        model: Quickshell.screens

        PanelWindow {
            required property var modelData
            screen: modelData
            anchors { top: true; bottom: true; left: true; right: true }
            exclusionMode: ExclusionMode.Ignore
            color: "black"
            WlrLayershell.layer: WlrLayer.Background
            WlrLayershell.namespace: "themely-backdrop"
            mask: Region {}

            Image {
                id: wall
                anchors.fill: parent
                source: "file://" + Quickshell.env("HOME") + "/.config/themely/current/wallpaper?" + backdrop.version
                fillMode: Image.PreserveAspectCrop
                cache: false
                asynchronous: true
                visible: false
            }

            MultiEffect {
                anchors.fill: parent
                source: wall
                blurEnabled: true
                blur: 0.5
                blurMax: 48
                opacity: 0.5
            }
        }
    }
}
