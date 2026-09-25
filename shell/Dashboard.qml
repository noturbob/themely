import Quickshell
import Quickshell.Io
import Quickshell.Widgets
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs

FloatingWindow {
    id: win
    required property var themes
    signal dismissed()
    signal edited()

    title: "themely"
    implicitWidth: 940
    implicitHeight: 580
    color: ui.bg
    onVisibleChanged: if (!visible) dismissed()

    // Form state. slug "" = new theme.
    property string slug: ""
    property string name: ""
    property string wallpaper: ""
    property bool newWallpaper: false
    property string accent: ""
    property real themeOpacity: 0.85
    property var swatches: []
    property var pal: ({})
    property string error: ""
    property bool confirmDelete: false
    readonly property var editing: themes.find(t => t.slug === slug) ?? null
    // The dashboard wears the palette being edited, so it recolors as you pick.
    readonly property var ui: pal.bg ? pal : ({ bg: "#1e1e2e", surface0: "#313244", surface1: "#45475a",
        overlay: "#6c7086", fg: "#cdd6f4", fg_muted: "#a6adc8", accent: "#89b4fa", accent2: "#74c7ec" })

    function edit(t) {
        slug = t.slug; name = t.name; wallpaper = t.wallpaper; newWallpaper = false
        accent = t.accent; themeOpacity = t.opacity; error = ""; confirmDelete = false
    }
    function clear() {
        slug = ""; name = ""; wallpaper = ""; newWallpaper = false
        accent = ""; themeOpacity = 0.85; swatches = []; error = ""; confirmDelete = false
    }
    function save() {
        const cmd = ["themely", "save", "--name", name, "--opacity", themeOpacity.toFixed(2)]
        if (accent) cmd.push("--accent", accent)
        if (newWallpaper) cmd.push("--wallpaper", wallpaper)
        if (slug) cmd.push("--slug", slug)
        error = ""
        saveProc.command = cmd
        saveProc.running = true
    }

    Component.onCompleted: {
        const cur = themes.find(t => t.current)
        if (cur) edit(cur)
    }
    // Set the command in the handler: a `command:` binding may not have updated yet when these fire.
    onWallpaperChanged: if (wallpaper) { swatchProc.command = ["themely", "swatches", wallpaper]; swatchProc.running = true }
    onAccentChanged: if (/^#[0-9a-f]{6}$/.test(accent)) { palProc.command = ["themely", "palette", accent]; palProc.running = true }

    Process {
        id: swatchProc
        stdout: StdioCollector {
            onStreamFinished: {
                try { win.swatches = JSON.parse(text) } catch (e) { return }
                if (win.newWallpaper) win.accent = win.swatches[0]  // automatic by default
            }
        }
    }
    Process {
        id: palProc
        stdout: StdioCollector { onStreamFinished: { try { win.pal = JSON.parse(text) } catch (e) {} } }
    }
    Process {
        id: saveProc
        stdout: StdioCollector {
            onStreamFinished: {
                const s = text.trim()
                if (!s) return
                const wasCurrent = win.editing?.current ?? false
                win.slug = s; win.newWallpaper = false
                win.edited()
                if (wasCurrent) Quickshell.execDetached(["themely", "apply", s])  // live-update the active theme
            }
        }
        stderr: StdioCollector { onStreamFinished: if (text.trim()) win.error = text.trim() }
    }
    Process {
        id: deleteProc
        command: ["themely", "delete", win.slug]
        stderr: StdioCollector { onStreamFinished: if (text.trim()) win.error = text.trim() }
        onExited: code => { if (code === 0) { win.clear(); win.edited() } }
    }

    FileDialog {
        id: picker
        title: "Choose a wallpaper"
        currentFolder: "file:///conf/wallpapers"
        nameFilters: ["Images (*.png *.jpg *.jpeg *.webp)"]
        onAccepted: {
            win.newWallpaper = true
            win.wallpaper = decodeURIComponent(selectedFile.toString().replace(/^file:\/\//, ""))
        }
    }

    Shortcut { sequence: "Escape"; onActivated: win.dismissed() }

    Pane {
        anchors.fill: parent
        padding: 22
        font.family: "Inter"
        palette.window: win.ui.bg
        palette.windowText: win.ui.fg
        palette.base: win.ui.surface0
        palette.text: win.ui.fg
        palette.button: win.ui.surface1
        palette.buttonText: win.ui.fg
        palette.highlight: win.ui.accent
        palette.highlightedText: win.ui.bg
        palette.placeholderText: win.ui.fg_muted
        background: Rectangle { color: win.ui.bg; Behavior on color { ColorAnimation { duration: 300 } } }

        RowLayout {
            anchors.fill: parent
            spacing: 22

            ColumnLayout {
                Layout.preferredWidth: 270
                Layout.fillHeight: true
                spacing: 12

                ListView {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    spacing: 10
                    clip: true
                    model: win.themes
                    delegate: ClippingRectangle {
                        id: row
                        required property var modelData
                        width: ListView.view.width
                        height: 92
                        radius: 14
                        color: win.ui.surface0
                        border.width: modelData.slug === win.slug ? 2 : 0
                        border.color: modelData.accent
                        Image {
                            anchors.fill: parent
                            source: "file://" + row.modelData.wallpaper
                            sourceSize.width: 540
                            fillMode: Image.PreserveAspectCrop
                            asynchronous: true
                            cache: false
                        }
                        Rectangle {
                            anchors.bottom: parent.bottom
                            width: parent.width
                            height: 30
                            color: Qt.rgba(0, 0, 0, 0.55)
                            Row {
                                x: 12
                                anchors.verticalCenter: parent.verticalCenter
                                spacing: 8
                                Rectangle {
                                    width: 10; height: 10; radius: 5
                                    anchors.verticalCenter: parent.verticalCenter
                                    color: row.modelData.accent
                                }
                                Text {
                                    text: row.modelData.name + (row.modelData.current ? "  ·  active" : "")
                                    color: "white"
                                }
                            }
                        }
                        TapHandler { onTapped: win.edit(row.modelData) }
                    }
                }
                Button { text: "+  New theme"; Layout.fillWidth: true; onClicked: win.clear() }
            }

            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: 10

                Label { text: "Name"; color: win.ui.fg_muted }
                TextField {
                    Layout.fillWidth: true
                    text: win.name
                    placeholderText: "Ocean night"
                    onTextEdited: win.name = text
                }

                Label { text: "Wallpaper"; color: win.ui.fg_muted }
                ClippingRectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 170
                    radius: 14
                    color: win.ui.surface0
                    Image {
                        anchors.fill: parent
                        source: win.wallpaper ? "file://" + win.wallpaper : ""
                        sourceSize.width: 1000
                        fillMode: Image.PreserveAspectCrop
                        asynchronous: true
                        cache: false
                    }
                    Label {
                        anchors.centerIn: parent
                        visible: !win.wallpaper
                        text: "Click to choose a wallpaper"
                        color: win.ui.fg_muted
                    }
                    TapHandler { onTapped: picker.open() }
                }

                Label { text: "Accent: picked from the wallpaper. Click another or type a hex."; color: win.ui.fg_muted }
                RowLayout {
                    spacing: 8
                    Repeater {
                        model: win.swatches
                        Rectangle {
                            required property string modelData
                            width: 30; height: 30; radius: 15
                            color: modelData
                            border.width: modelData === win.accent ? 3 : 0
                            border.color: win.ui.fg
                            TapHandler { onTapped: win.accent = parent.modelData }
                        }
                    }
                    TextField {
                        Layout.preferredWidth: 110
                        text: win.accent
                        placeholderText: "#89b4fa"
                        validator: RegularExpressionValidator { regularExpression: /#?[0-9a-fA-F]{0,6}/ }
                        onEditingFinished: win.accent = (text.startsWith("#") ? text : "#" + text).toLowerCase()
                    }
                }

                Label { text: "Opacity  " + Math.round(win.themeOpacity * 100) + "%"; color: win.ui.fg_muted }
                Slider {
                    Layout.fillWidth: true
                    from: 0.3; to: 1.0; stepSize: 0.01
                    value: win.themeOpacity
                    onMoved: win.themeOpacity = value
                }

                Row {
                    spacing: 6
                    Repeater {
                        model: ["bg", "surface0", "surface1", "overlay", "fg_muted", "fg", "accent", "accent2"]
                        Rectangle {
                            required property string modelData
                            width: 40; height: 28; radius: 8
                            color: win.pal[modelData] ?? "transparent"
                            border.color: win.ui.overlay
                        }
                    }
                }

                Label { visible: win.error; text: win.error; color: "#f38ba8"; wrapMode: Text.Wrap; Layout.fillWidth: true }
                Item { Layout.fillHeight: true }

                RowLayout {
                    Button {
                        text: win.slug ? "Save" : "Create"
                        enabled: win.name.trim() && win.wallpaper && !saveProc.running
                        onClicked: win.save()
                    }
                    Button {
                        visible: win.slug && !(win.editing?.current ?? false)
                        text: win.confirmDelete ? "Really delete?" : "Delete"
                        onClicked: win.confirmDelete ? (deleteProc.running = true) : (win.confirmDelete = true)
                    }
                }
            }
        }
    }
}
