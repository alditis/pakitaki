import re
import os
import ntpath
import datetime
from gi.repository import RB
from urllib.request import url2pathname

from util import const

def generate_folder_tmp(path):
    dt = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    folder_tmp = url2pathname(path).replace('file:///', '/')
    folder_tmp +=  '/.tmp_' + dt + '/'

    if not os.path.exists(folder_tmp):
        os.makedirs(folder_tmp)

    return folder_tmp

def is_allow_file_format(entry):

    is_allow = False

    file_path = entry.get_string(RB.RhythmDBPropType.LOCATION)
    file_format = get_file_format(file_path)

    if file_format in const.OUTPUT_FORMATS:
        is_allow = True

    return is_allow

def get_file_format(file_path):
    return os.path.splitext(file_path)[1][1:].strip().lower()

def get_convert_param(output_format):
    convert_param = ''

    if output_format == const.FORMAT_OGG:
        convert_param = '-c:a libvorbis -q:a 4'
    elif output_format == const.FORMAT_MP3:
        convert_param = '-acodec libmp3lame'

    return convert_param

def get_abspath_entry(entry):
    abspath_entry = entry.get_string(RB.RhythmDBPropType.LOCATION)
    abspath_entry = url2pathname(abspath_entry).replace('file:///', '/')
    return abspath_entry

def get_abspath_fragment(abspath_entry, path_fragments):
    filename = get_filename_fragment(abspath_entry)
    filename = path_fragments + filename
    return filename

def get_filename_fragment(abspath_entry):
    filename = ntpath.basename(abspath_entry)
    filename = filename.replace(' ', '_')
    filename = filename.replace('-', '_')
    filename = re.sub('[!^\!\/@\?\¿\n\. \'\(\)\[\]\{\}\+\*\$\%\~\,\:\;](?=[^.]*\.)', '', filename)
    filename = re.sub(r'(\_)\1+', r'\1', filename)
    filename = 'pktk_' + filename.lower()
    return filename

def get_destination_result(settings, number_fragments):
    """Get final destination for result of join fragment songs."""

    return (settings['output-folder'] + '/' +
            const.NAME_RESULT + str(number_fragments) + '_songs_' +
            datetime.datetime.now().strftime("%y%m%d-%H%M%S") +
            '.' + settings['output-format'])

def get_filter_complex(index, number_fragments):
    """Get parcial filter_complex on base the number iteration and number of fragment songs."""
    filter_complex = ''
    post = ''

    if index == 0:
        pre = '[0][1]'
        if number_fragments != const.NUMBER_SONGS_MIN:
            post = '[01];'
    else:
        pre = '[0'+ str(index) +'][' + str(index + 1) + ']'
        if index != number_fragments - const.NUMBER_SONGS_MIN:
            post = '[0' + str(index + 1) + '];'

    if index <= number_fragments - const.NUMBER_SONGS_MIN:
        filter_complex = pre + 'acrossfade=d=' + str(const.DURATION_ACROSSFADE) + ':c1=tri:c2=tri' + post

    return filter_complex