import os
import threading
import traceback

from gi.repository import Gtk, GLib

from pychess.compat import StringIO
from pychess.System.Log import log
from pychess.perspectives import Perspective, perspective_manager
from pychess.perspectives.database.gamelist import GameList
from pychess.perspectives.database.OpeningTreePanel import OpeningTreePanel
from pychess.perspectives.database.FilterPanel import FilterPanel
from pychess.perspectives.database.PreviewPanel import PreviewPanel
from pychess.System.prefix import addDataPrefix, addUserConfigPrefix
from pychess.widgets.pydock.PyDockTop import PyDockTop
from pychess.widgets.pydock import EAST, SOUTH, CENTER
from pychess.widgets import dock_panel_tab
from pychess.widgets.ionest import game_handler
from pychess.Database.PgnImport import PgnImport
from pychess.Database.model import engine, metadata


class Database(Perspective):
    def __init__(self):
        Perspective.__init__(self, "database", _("Database"))

    def create_toolbuttons(self):
        self.import_button = Gtk.ToolButton.new_from_stock(Gtk.STOCK_CONVERT)
        self.import_button.set_tooltip_text(_("Import PGN file"))
        self.import_button.connect("clicked", self.on_import_clicked)

        self.close_button = Gtk.ToolButton.new_from_stock(Gtk.STOCK_CLOSE)
        self.close_button.set_tooltip_text(_("Close"))
        self.close_button.connect("clicked", self.close)

    def open_chessfile(self, filename):
        perspective_widget = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        perspective_manager.set_perspective_widget("database", perspective_widget)

        self.gamelist = GameList(filename)
        self.opening_tree_panel = OpeningTreePanel(self.gamelist)
        self.filter_panel = FilterPanel(self.gamelist)
        self.preview_panel = PreviewPanel(self.gamelist)

        self.progressbar = Gtk.ProgressBar(show_text=False)

        perspective = perspective_manager.get_perspective("database")

        self.dock = PyDockTop("database", perspective)
        align = Gtk.Alignment()
        align.show()
        align.add(self.dock)
        self.dock.show()
        perspective_widget.pack_start(align, True, True, 0)

        dockLocation = addUserConfigPrefix("pydock-database.xml")

        docks = {
            "gamelist": (Gtk.Label(label="gamelist"), self.gamelist.box),
            "openingtree": (dock_panel_tab(_("Opening tree"), "", addDataPrefix("glade/panel_docker.svg")), self.opening_tree_panel.box),
            "filter": (dock_panel_tab(_("Filter"), "", addDataPrefix("glade/panel_docker.svg")), self.filter_panel.box),
            "preview": (dock_panel_tab(_("Preview"), "", addDataPrefix("glade/panel_docker.svg")), self.preview_panel.box),
        }

        if os.path.isfile(dockLocation):
            try:
                self.dock.loadFromXML(dockLocation, docks)
            except Exception as e:
                stringio = StringIO()
                traceback.print_exc(file=stringio)
                error = stringio.getvalue()
                log.error("Dock loading error: %s\n%s" % (e, error))
                msg_dia = Gtk.MessageDialog(None,
                                            type=Gtk.MessageType.ERROR,
                                            buttons=Gtk.ButtonsType.CLOSE)
                msg_dia.set_markup(_(
                    "<b><big>PyChess was unable to load your panel settings</big></b>"))
                msg_dia.format_secondary_text(_(
                    "Your panel settings have been reset. If this problem repeats, \
                    you should report it to the developers"))
                msg_dia.run()
                msg_dia.hide()
                os.remove(dockLocation)
                for title, panel in docks.values():
                    title.unparent()
                    panel.unparent()

        if not os.path.isfile(dockLocation):
            leaf = self.dock.dock(docks["gamelist"][1], CENTER, docks["gamelist"][0], "gamelist")
            leaf.setDockable(False)

            leaf = leaf.dock(docks["filter"][1], EAST, docks["filter"][0], "filter")
            leaf = leaf.dock(docks["openingtree"][1], SOUTH, docks["openingtree"][0], "openingtree")
            leaf.dock(docks["preview"][1], SOUTH, docks["preview"][0], "preview")

        def unrealize(dock):
            dock.saveToXML(dockLocation)
            dock._del()

        self.dock.connect("unrealize", unrealize)

        self.dock.show_all()
        perspective_widget.show_all()

        if filename.endswith(".pdb"):
            perspective_manager.set_perspective_toobuttons("database", [self.import_button, self.close_button])
        else:
            perspective_manager.set_perspective_toobuttons("database", [self.close_button])
        perspective_manager.activate_perspective("database")

    def close(self, widget):
        self.gamelist.chessfile.close()
        perspective_manager.disable_perspective("database")

    def on_import_clicked(self, widget):
        opendialog, savedialog, enddir, savecombo, savers = game_handler.getOpenAndSaveDialogs()
        response = opendialog.run()
        if response == Gtk.ResponseType.ACCEPT:
            filename = opendialog.get_filename()
            self.do_import(filename)
        opendialog.hide()

    def do_import(self, filename):
        self.gamelist.progress_dock.add(self.progressbar)
        self.gamelist.progress_dock.show_all()

        def importing():
            # TODO:
            if 0:
                metadata.drop_all(engine)
                metadata.create_all(engine)
            importer = PgnImport()
            importer.do_import(filename, self.progressbar)
            GLib.idle_add(self.gamelist.progress_dock.remove, self.progressbar)
            GLib.idle_add(self.gamelist.load_games)

        thread = threading.Thread(target=importing)
        thread.daemon = True
        thread.start()