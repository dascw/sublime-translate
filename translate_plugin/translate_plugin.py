"""
Requests translation of comment selected by user using Google's translate API; replaces comment with result.
"""
import sublime
import sublime_plugin
import json
import ast # required for expansion of string list literals from sublime settings.
import threading 
import sys 
import os

# path append is required to add site-packages (all dependencies) to path for google modules.
if sys.platform == 'linux2' or sys.platform == 'linux':
    path = sublime.packages_path()
    ## @not in some instances, packages_path() returns empty string. 
    ## If string is empty, attempt to extract path from expected location in system path.
    ## @note this is not guaranteed to work and may result in undefined behaviour on some systems.
    if not path:
        path = sys.path[3]

    sys.path.append(os.path.join(path + "/Translate/site-packages/"))
elif int(sublime.version()) > 3000: # windows path in sublime text 3.
    sys.path.append(sublime.packages_path() + "\\Translate\\site-packages\\")
else:
    # windows
    sys.path.append(os.path.join(sublime.packages_path() + "\\Translate\\site-packages\\"))

from googleapiclient.discovery import build 

__author__      = '(Sean Whittaker)'
__version__     = '1.0.6'
__verbose__     = False


def print_verbose(string_arg):
    """Verbose print, set debug to true to print debug info

    Args:
        string_arg (str): string to print.
    """
    if __verbose__ == True:
        print(string_arg)


class TranslateCommand(sublime_plugin.TextCommand):
    """Executed command called by user, parses text selected by user and returns translation.
    
    Text is translated according to conditions read from settings.
    NOTE Extends TextCommand so that run() receives a View to modify.
    Args:
        edit (object Sublime): edit region (buffered txt file) containing link to translation text.
    """
    def run(self, edit={}):
        global __verbose__
        print('Running translate plugin')
        region      = self.view.sel()
        settings    = HandleSettings()
        __dev_key   = settings.values.get('tran_key')
        source      = settings.values.get('source_language') # get language settings from configuration file.
        target      = settings.values.get('target_language')
        __verbose__ = settings.values.get('debug') # for print verbose.
        threads     = [] 

        for coord in region:
            print('Regions detected: {}'.format((coord))) # prints the coordinates of region in characters.
            if coord.empty():
                print('No text detected.')
            else:
                # replace text
                line = self.view.substr(coord)
                # @note we need to store size of line too.
                tran_obj = GoogleTran(__dev_key, self._strip_special_symbols(line))
                thread = ApiThreadCall(coord, tran_obj, source, target)
                threads.append(thread)
                thread.start()

        handle_thread(threads)
        
        offset = 0
        print_verbose('# Length of threads: {}'.format(str(len(threads))))
        for thread in threads: #  @note can this be for in ranage instead?
            # @note we were getting confused here!!!
            # we needed to adjust regions based on mutliple cursor points, otherwise each time the region was
            # updated with a size different than original text, we'd get lost (regions defined by num of chars)
            print_verbose('# Region for result: {}'.format((thread.region)))
            if thread.result == None:
                print_verbose('# Translation failed! No result.')
                continue
            # @note fix added after bug reported by Cesar #3.
            thread.result = self._fix_comment_blocks(thread.result)
            print('Translate result: {}.'.format(thread.result))
            siz_dif = (thread.obj.length - len(thread.result) )
            # update region!
            thread.region = sublime.Region(thread.region.begin() - offset, thread.region.end() - offset)
            print_verbose('# Offset = {}'.format(str(offset)))
            print_verbose('# New region: {}'.format(str(thread.region)))
            offset+=siz_dif
            self.view.replace(edit, thread.region, thread.result)

    def _fix_comment_blocks(self, arg):
        """Fixes C style comment blocks when found in a selection.

        Google Translate API breaks C style comment block formatting when parsed.
        To fix this, we simply replace the broken comment blocks with fixed comment blocks
        if they exist. (not the most elegant fix, but works.)

        Args:
            arg (str): result from translation.
        """
        print_verbose('Comment block pre: {}'.format(arg))
        arg = arg.replace('/ *', '/*') # fix comment block issue with google tran.
        arg = arg.replace('* /', '*/')
        print_verbose('Comment block post: {}'.format(arg))
        return arg

    def _strip_special_symbols(self, arg):
        """Strips out all special symbols found inside the string (arugment) parsed.
        Replaces any symbols found with space character.
        This provides parsing of function/variable names.

        Args:
            arg (str): string pre translation.
            special_symbsol (object Sublime.Settings): all symbols to remove from string.
        """
        special_symbols = ast.literal_eval(HandleSettings().values.get('special_symbols'))
        for symbol in special_symbols:
            if arg.find(symbol) != -1: # char found
                print_verbose('# Special symbol found: {}'.format(symbol))
                arg = arg.replace(symbol, ' ') # replace with space
        return arg


class ApiThreadCall(threading.Thread):
    """Class for managing threaded translate.

    As advised by https://developers.google.com/api-client-library/python/guide/thread_safety
    Threading is easily achieved by creating a new object. This is because the Google API
    requests are not thread safe!
    Thread execution is delcared in run() member function, thread.start() is required
    to call.

    Args:
        region (object Region): contains coordinates of selected region in sublime.
        tran_obj (object GoogleTran): contains raw string, api key, execute method.
        source_language (str): language to translate from.
        target_language (str): langauge to translate to.
    """
    def __init__(self, region, tran_obj, source_language, target_language, timeout=5):
        self.timeout    = timeout
        self.region     = region
        self.obj        = tran_obj # we run this with .start()
        self.result     = None
        self.source     = source_language
        self.target     = target_language
        threading.Thread.__init__(self)

    def run(self):
        self.result = self.obj.execute(self.source, self.target)['translations'][0]['translatedText']
        return


def handle_thread(threads):
    """loop through threads, execute handshake and append.

    Args:
        threads (object Threads): contains all translation threads.
    """
    print('Handling all threads.')
    
    while True:
        next_threads = []
        for thread in threads:
            if thread.is_alive():
                next_threads.append(thread)
        if not next_threads: 
            break
        else:
            threads = next_threads
    print('All threads handled.')


class GoogleTran(object):
    """Returns object for translation.
    An object is created each time a translation request is desired in order
    to allow safe threading with the google API.

    Args:
        api_key (str): API key for google cloud.
        raw_str (str): raw string to translate.
    """
    def __init__(self, api_key, raw_str):
        self.key        = api_key
        self.service    = build('translate', 'v2', developerKey=self.key)
        self.raw_str    = raw_str
        self.length     = len(raw_str) # store length
        self.result     = []         
        print_verbose('raw_str: {}'.format(raw_str))
        
    def execute(self, source_language, target_language):
        """Params are service object (resulting from handshake with GoogleTran
        Raw string for translation (@note no comment lines/special symbols?)

        Args:
            source_language (str): language to translate from.
            target_language (str): language to translate to.
        """
        # translate object.
        self.result = self.service.translations().list(
                    source=source_language,
                    target=target_language,
                    q=[self.raw_str]
                    ).execute()
        return self.result


class HandleSettings(sublime_plugin.ApplicationCommand):
    """Returns settings object for manipulation/reference"""
    def __init__(self, arg='translate.sublime-settings'):
        self.values = sublime.load_settings(arg)

