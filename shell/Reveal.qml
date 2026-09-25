import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import QtQuick
import QtQuick.Effects

// freeze every output → apply under the frozen frame → grow a hole from the picked card.
Scope {
    id: reveal
    property string phase: "idle"   // idle → wait → capture → apply → grow
    property string slug: ""
    property point origin: Qt.point(0, 0)
    property int captured: 0
    signal finished()

    function start(s, x, y) {
        if (phase !== "idle") return
        slug = s; origin = Qt.point(x, y); captured = 0
        phase = "wait"
        unmapDelay.start()
    }
    function captureDone() {
        if (phase === "capture" && ++captured >= Quickshell.screens.length) runApply()
    }
    function runApply() {
        if (phase !== "capture") return
        captureTimeout.stop()
        phase = "apply"
        apply.running = true
    }

    Timer { id: unmapDelay; interval: 90; onTriggered: { reveal.phase = "capture"; captureTimeout.start() } }
    Timer { id: captureTimeout; interval: 800; onTriggered: reveal.runApply() }  // never hang on a stuck screencopy
    Timer { id: settle; interval: 250; onTriggered: { reveal.phase = "grow"; done.start() } }
    Timer { id: done; interval: 760; onTriggered: { reveal.phase = "idle"; reveal.finished() } }

    Process {
        id: apply
        command: ["themely", "apply", reveal.slug]
        stderr: StdioCollector { id: err }
        onExited: code => {
            if (code !== 0)
                Quickshell.execDetached(["notify-send", "-a", "themely", "Some apps didn't switch", err.text])
            settle.start()
        }
    }

    Variants {
        model: reveal.phase === "idle" || reveal.phase === "wait" ? [] : Quickshell.screens

        PanelWindow {
            id: win
            required property var modelData
            screen: modelData
            anchors { top: true; bottom: true; left: true; right: true }
            exclusionMode: ExclusionMode.Ignore
            color: "transparent"
            WlrLayershell.layer: WlrLayer.Overlay
            WlrLayershell.namespace: "themely-reveal"

            // Origin on this output, clamped: other outputs grow from their nearest edge point.
            readonly property real ox: Math.max(0, Math.min(width, reveal.origin.x - modelData.x))
            readonly property real oy: Math.max(0, Math.min(height, reveal.origin.y - modelData.y))
            readonly property real maxR: Math.hypot(Math.max(ox, width - ox), Math.max(oy, height - oy)) + 40
            property real r: 0
            NumberAnimation on r {
                running: reveal.phase === "grow"
                from: 0; to: win.maxR
                duration: 700
                easing.type: Easing.InOutCubic
            }

            ScreencopyView {
                id: frozen
                anchors.fill: parent
                captureSource: win.modelData
                live: false
                visible: false
                onHasContentChanged: if (hasContent) reveal.captureDone()
            }

            Item {
                id: hole
                anchors.fill: parent
                visible: false
                layer.enabled: true
                Rectangle {
                    x: win.ox - win.r; y: win.oy - win.r
                    width: win.r * 2; height: win.r * 2
                    radius: win.r
                    color: "black"
                }
            }

            MultiEffect {
                anchors.fill: parent
                source: frozen
                visible: frozen.hasContent
                maskEnabled: true
                maskInverted: true
                maskSource: hole
                maskThresholdMin: 0.5
                maskSpreadAtMin: 0.3
            }
        }
    }
}
