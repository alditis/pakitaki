# coding=utf-8

# PakiTaki Rhythmbox Plugin

# alditis <alditis@gmail.com>, 2017
# License MIT

import gi
gi.require_version('Gtk', '3.0')

import os
import rb
import time
import ntpath
import random
import datetime
import threading
from ffmpy import FFmpeg
from gi.repository import GObject, RB, Peas, Gtk, Gio

from util import const
from util import helper
from util import progressbar

class PakiTakiPlugin (GObject.Object, Peas.Activatable):

    object = GObject.property(type=GObject.Object)

    def __init__(self):
        super(PakiTakiPlugin, self).__init__()

    def do_activate(self):
        self.shell = self.object
        self.config()
        self.menu_build()

    def config(self):
        self.settings = Gio.Settings(const.APP_SCHEMA)

    def menu_build(self):
        self.action_name = const.APP_NAME + 'Action'

        self.action = Gio.SimpleAction.new(self.action_name, None)
        self.action.connect('activate', self.window_build)
        self.action.label = const.APP_NAME

        self.item = Gio.MenuItem()
        self.item.set_label(self.action.label)
        self.item.set_detailed_action('app.' + self.action_name)

        self.app = Gio.Application.get_default()
        self.app.add_action(self.action)
        self.app.add_plugin_menu_item('view', 'view' + self.action_name, self.item)

    def window_build(self, action, data):

        def set_source_songs(combo_box):
            tree_iter = combo_box.get_active_iter()

            if tree_iter != None:
                model = combo_box.get_model()
                self.source = model[tree_iter][:2][1]

        def set_number_songs(spin_button):
            self.settings['number-songs'] = spin_button.get_value()

        def set_start_min(spin_button):
            self.settings['start-min'] = spin_button.get_value()

        def set_start_max(spin_button):
            self.settings['start-max'] = spin_button.get_value()

        def set_duration_min(spin_button):
            self.settings['duration-min'] = spin_button.get_value()

        def set_duration_max(spin_button):
            self.settings['duration-max'] = spin_button.get_value()

        def set_output_folder(button):
            self.settings['output-folder'] = button.get_uri()

        def set_output_format(combo_box):
            output_format = combo_box.get_active_text()

            if output_format != None:
                self.settings['output-format'] = output_format

        def set_process(button):
            self.process_thread = threading.Thread(target = self.process)
            self.process_thread.daemon = True
            self.process_thread.start()
            self.process_thread_finish = threading.Event()

        def autoscroll(scrolled_window, *args):
            adj = scrolled_window.get_vadjustment()
            adj.set_value(adj.get_upper() - adj.get_page_size())

        self.configure_callback_dic = {
            "rb_pakitaki_source_songs_changed": set_source_songs,
            "rb_pakitaki_number_songs_changed": set_number_songs,
            "rb_pakitaki_start_min_changed": set_start_min,
            "rb_pakitaki_start_max_changed": set_start_max,
            "rb_pakitaki_duration_min_changed": set_duration_min,
            "rb_pakitaki_duration_max_changed": set_duration_max,
            "rb_pakitaki_output_folder_changed": set_output_folder,
            "rb_pakitaki_output_format_changed": set_output_format,
            "rb_pakitaki_process_clicked": set_process,
            "rb_pakitaki_scroll_size_allocate": autoscroll
        }

        builder = Gtk.Builder()
        builder.add_from_file(rb.find_plugin_file(self, const.APP_UI))

        window = builder.get_object("window")
        window.connect("delete-event", Gtk.main_quit)

        source_list = self.generate_source_list()
        source_combobox = builder.get_object("rb_pakitaki_source_songs")
        source_combobox.set_model(source_list)

        output_format_list = self.generate_output_format_list()
        output_format_combobox = builder.get_object("rb_pakitaki_output_format")
        output_format_combobox.set_model(output_format_list)
        output_format_combobox.set_active(const.OUTPUT_FORMATS.index(self.settings['output-format']))

        self.report = builder.get_object("rb_pakitaki_report")
        self.report_scroll = builder.get_object("rb_pakitaki_scroll")
        self.report_buffer = self.report.get_buffer()

        plugin_path = os.path.dirname(__file__)
        plugin_logo = os.path.join(plugin_path, const.APP_LOGO)

        builder.get_object("rb_pakitaki_logo").set_from_file(plugin_logo)
        builder.get_object("rb_pakitaki_number_songs").set_value(self.settings['number-songs'])
        builder.get_object("rb_pakitaki_start_min").set_value(self.settings['start-min'])
        builder.get_object("rb_pakitaki_start_max").set_value(self.settings['start-max'])
        builder.get_object("rb_pakitaki_duration_min").set_value(self.settings['duration-min'])
        builder.get_object("rb_pakitaki_duration_max").set_value(self.settings['duration-max'])
        builder.get_object("rb_pakitaki_output_folder").set_uri(self.settings['output-folder'])

        self.progressbar = builder.get_object("rb_pakitaki_progress_bar")
        self.button_process = builder.get_object("rb_pakitaki_process")

        builder.connect_signals(self.configure_callback_dic)
        window.show()
        Gtk.main()

    def generate_source_list(self):
        sources = Gtk.ListStore(str, object)
        sources.append([const.SOURCE_ALL_SONGS, None])

        playlists = self.shell.props.playlist_manager.get_playlists()

        for pl in playlists:
            number_songs = len(pl.get_query_model())

            if number_songs >= const.NUMBER_SONGS_MIN:
                sources.append([pl.props.name, pl])

        return sources

    def generate_output_format_list(self):
        output_format_list = Gtk.ListStore(str)

        for allow_format in const.OUTPUT_FORMATS:
            output_format_list.append([allow_format])

        return output_format_list

    def process(self):
        progressbar.start(self)
        self.done = False
        self.progress = 0

        path_fragments = helper.generate_folder_tmp(self.settings['output-folder'])
        fragments = self.get_fragments(path_fragments)
        self.join_fragments(fragments)
        self.delete_tmp_files(fragments, path_fragments)

    def get_fragments(self, path_fragments):
        """Get fragment songs randomly."""

        self.report_buffer.insert_at_cursor("-----------------------------\n")
        self.report_buffer.insert_at_cursor("-- Fragments\n")
        self.report_buffer.insert_at_cursor("-----------------------------\n")
        self.report_buffer.insert_at_cursor("Fragments saved in folder: " + path_fragments + "\n")

        if self.source == None:
            query_model = self.shell.props.library_source.props.base_query_model
        else:
            query_model = self.source.get_query_model()

        query_model.shuffle_entries()
        total_entries = query_model.get_size()

        if int(self.settings['number-songs']) > total_entries:
            number_songs = total_entries
        else:
            number_songs = int(self.settings['number-songs'])

        # For progressbar
        factor_task_fragment = const.PERCENTAGE_TASK_FRAGMENT / number_songs

        songs = []
        i = 0

        for row in query_model:
            if i < number_songs:
                is_allow = helper.is_allow_file_format(row[0])
                if is_allow:
                    fragment_song = self.generate_fragment_song(row[0], path_fragments)
                    if fragment_song != None:
                        songs.append(fragment_song)
                        self.progress += factor_task_fragment
                        i += 1

                        self.report_buffer.insert_at_cursor("[" + str(i) + "] " + ntpath.basename(fragment_song) + "\n")
                    else:
                        self.report_buffer.insert_at_cursor("[Error] " + ntpath.basename(row[0].get_string(RB.RhythmDBPropType.LOCATION)) + "\n")
            else:
                break

        return songs

    def generate_fragment_song(self, entry, path_fragments):
        """Fragment song and send to temporal destination."""
        start = random.randint(int(self.settings['start-min']), int(self.settings['start-max']))
        duration = random.randint(int(self.settings['duration-min']), int(self.settings['duration-max']))
        duration_entry = entry.get_ulong(RB.RhythmDBPropType.DURATION)

        if duration_entry >= start + duration:
            abspath_entry = helper.get_abspath_entry(entry)
            abspath_fragment = helper.get_abspath_fragment(abspath_entry, path_fragments)

            ff = FFmpeg(
                inputs = {abspath_entry: None},
                outputs = {abspath_fragment: '-nostats -vn -loglevel 0 -ss ' + str(start) + ' -t ' + str(duration)}
            )
            try:
                ff.run()
            except Exception as e:
                os.remove(abspath_fragment)
                abspath_fragment = None
        else:
            abspath_fragment = None

        return abspath_fragment

    def join_fragments(self, fragments):
        """Join fragment songs and send result to final destination."""

        self.report_buffer.insert_at_cursor("\n-----------------------------\n")
        self.report_buffer.insert_at_cursor("-- Join\n")
        self.report_buffer.insert_at_cursor("-----------------------------\n")

        number_fragments = len(fragments)

        self.report_buffer.insert_at_cursor("Total fragments: " + str(number_fragments) +"\n")
        self.report_buffer.insert_at_cursor("Init join\n")

        # For progressbar
        self.factor_task_join = const.PERCENTAGE_TASK_JOIN / number_fragments
        self.factor_task_delete = const.PERCENTAGE_TASK_DELETE / number_fragments
        self.progress += self.factor_task_join

        ##############################################
        # Example of filter_complex for 4 fragments:
        ##############################################
        # [0][1]acrossfade=d=3:c1=tri:c2=tri[01];
        # [01][2]acrossfade=d=3:c1=tri:c2=tri[02];
        # [02][3]acrossfade=d=3:c1=tri:c2=tri
        ##############################################
        filter_complex = ''
        inputs = {}
        index = 0

        for p in fragments:
            inputs[p] = None
            filter_complex += helper.get_filter_complex(index, number_fragments)
            index += 1

        self.result = helper.get_destination_result(self.settings, number_fragments)
        convert = helper.get_convert_param(self.settings['output-format'])

        options = ('-nostats -loglevel 0 -y -filter_complex "' + filter_complex +
                    '" -b:a ' + const.BITRATE + ' -map_metadata -1' +
                    ' -metadata album="' + const.APP_NAME + '" -metadata artist="' + const.TAG_ARTIST +
                    '" -metadata date="' + const.TAG_YEAR + '" ' + convert + ' -c:v copy')
        ff = FFmpeg(
            inputs = inputs,
            outputs = {self.result: options}
        )
        try:
            ff.run()
        except Exception as e:
            print("Error in join")
            print(repr(e))

        self.report_buffer.insert_at_cursor("Finish join\n")

    def delete_tmp_files(self, fragments, path_fragments):
        """Delete fragment songs of destination."""

        self.report_buffer.insert_at_cursor("\n-----------------------------\n")
        self.report_buffer.insert_at_cursor("-- Clean\n")
        self.report_buffer.insert_at_cursor("-----------------------------\n")

        # For progressbar
        self.task = const.TASK_DELETE
        self.progress += self.factor_task_delete

        self.report_buffer.insert_at_cursor("Delete temporary files.\n")

        for p in fragments:
            os.remove(p)

        self.report_buffer.insert_at_cursor("Delete temporary path.\n")

        if os.path.exists(path_fragments):
            os.removedirs(path_fragments)

        self.report_buffer.insert_at_cursor("\n-----------------------------\n")
        self.report_buffer.insert_at_cursor("-- Result\n")
        self.report_buffer.insert_at_cursor("-----------------------------\n")
        self.report_buffer.insert_at_cursor("Song created:" + "\n")
        self.report_buffer.insert_at_cursor(self.result.replace('file:///', '/') + "\n")

    def do_deactivate(self):
        self.app.remove_plugin_menu_item('view', 'view' + self.action_name)
        del self.shell
        del self.item
        del self.action
        del self.settings
        del self.process_thread_finish
        del self.progressbar_thread_finish