"""
Requests translation of comment parsed to to plugin via user selection
using google translate API and replaces comment with result.
"""
# Required for Sublime API
import sublime
import sublime_plugin
import json
import ast # required for expansion of string list literals from sublime settings.
import threading # required for threading.

# required for reference google API
import sys
import os
# path append is required to add site-packages (all dependencies) to path for google modules.
# linux path
if sys.platform == 'linux2':
    sys.path.append(os.path.join(sublime.packages_path() + "/Translate/site-packages/"))
elif int(sublime.version()) > 3000: # windows path in sublime text 3.
    sys.path.append(sublime.packages_path() + "\\Translate\\site-packages\\")
else:
    # path for windows in sublime text 2
    sys.path.append(os.path.join(sublime.packages_path() + "\\Translate\\site-packages\\"))

from googleapiclient.discovery import build       # required for google api access

__author__ = '(Sean Whittaker)'
__version__ = '1.0.6'
__verbose__  = False

# Extends TextCommand so that run() receives a View to modify.
class TranslateCommand(sublime_plugin.TextCommand):
    """Executed command called by user, parses text selected by user and replaces
    text with desired translation as read in settings.

    Args:
        edit (object Sublime): edit region (buffered txt file) containing link to translation text.
    """
    def run(self, edit):
        global __verbose__
        print('Running translate plugin')
        region = self.view.sel()
        settings = HandleSettings('translate.sublime-settings')
        __devKey__ = settings.values.get('tran_key')
        source = settings.values.get('source_language') # get language settings from configuration file.
        target = settings.values.get('target_language')
        __verbose__ = settings.values.get('debug') # for print verbose.
        threads = [] # empty threads
        for idx in range(len(region)):
            print('Regions detected'  + str(region[idx])) # prints the coordinates of region in characters.
            if region[idx].empty() == True:
                print('No text detected.')
            else:
                # replace text
                line = self.view.substr(region[idx])
                # @note we need to store size of line too.
                tran_obj = GoogleTran(__devKey__, self.stripSpecialSymbols(line))
                thread = ApiThreadCall(region[idx], tran_obj, source, target)
                threads.append(thread)
                thread.start()

        # old handle threads mode..
        handleThreads(threads)
        #self.handle_threads(threads)
        offset = 0
        print_verb('# Length of threads: ' + str(len(threads)))
        for tdx in (range(len(threads))):
            # @note we were getting confused here!!!
            # we needed to adjust regions based on mutliple cursor points, otherwise each time the region was
            # updated with a size different than original text, we'd get lost (regions defined by num of chars)
            print_verb('# Region for result: ' + str(threads[tdx].region))
            if threads[tdx].result == None:
                print_verb('# Translation failed! No result.')
                continue
            # @note fix added after bug reported by Cesar #3.
            threads[tdx].result = self.fixCommentBlocks(threads[tdx].result)
            print('Translate result: ' + threads[tdx].result + '.')
            siz_dif = (threads[tdx].obj.length - len(threads[tdx].result) )
            # update region!
            threads[tdx].region = sublime.Region(threads[tdx].region.begin() - offset, threads[tdx].region.end() - offset)
            print_verb('# Offset = ' + str(offset))
            print_verb('# New region: ' + str(threads[tdx].region))
            offset+=siz_dif
            self.view.replace(edit, threads[tdx].region, threads[tdx].result)
    def fixCommentBlocks(self, arg):
        """Google Translate API breaks C style comment block formatting when parsed.
        To fix this, we simply replace the broken comment blocks with fixed comment blocks
        if they exist. (not the most elegant fix, but works.)

        Args:
            arg (str): result from translation.
        """
        print_verb('Comment block pre: ' + arg)
        arg = arg.replace('/ *', '/*') # fix comment block issue with google tran.
        arg = arg.replace('* /', '*/')
        print_verb('Comment block post: ' + arg)
        return arg
    def stripSpecialSymbols(self, arg):
        """Strips out all special symbols found inside the string (arugment) parsed.
        Replaces any symbols found with space character.
        This provides parsing of function/variable names.

        Args:
            arg (str): string pre translation.
            special_symbsol (object Sublime.Settings): all symbols to remove from string.
        """
        special_symbols = ast.literal_eval(HandleSettings('translate.sublime-settings').values.get('special_symbols'))
        for idx in range(len(special_symbols)):
            if arg.find(special_symbols[idx]) != -1: # char found
                print_verb('# Special symbol found: ' + special_symbols[idx])
                arg = arg.replace(special_symbols[idx], ' ') # replace with space
        return arg


def print_verb(string_arg):
    """Verbose print, set debug to true to print debug info

    Args:
        string_arg (str): string to print.
    """
    if __verbose__ == True:
        print(string_arg)


class ApiThreadCall(threading.Thread):
    """As advised by https://developers.google.com/api-client-library/python/guide/thread_safety
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
        self.timeout = timeout;
        self.region = region;
        self.obj = tran_obj; # we run this with .start()
        self.result = None;
        self.source = source_language;
        self.target = target_language;
        threading.Thread.__init__(self);
    def run(self):
        self.result = self.obj.execute(self.source, self.target)['translations'][0]['translatedText']
        return


def handleThreads(threads):
    """loop through threads, execute handshake and append.

    Args:
        threads (object Threads): contains all translation threads.
    """
    print('Handling all threads...')
    temp_threads = threads # local copy
    while True:
        next_threads = []
        for thread in temp_threads:
            if thread.is_alive():
                next_threads.append(thread)
        #print(' - Threads still up: ' + str(len(next_threads)) + '.')
        if len(next_threads) == 0:      # break when no threads left.
            break
        else:
            temp_threads = next_threads # set and continue
    print('All threads handled.')


class GoogleTran():
    """Returns object for translation.
    An object is created each time a translation request is desired in order
    to allow safe threading with the google API.

    Args:
        pKey (str): API key for google cloud.
        stRaw (str): raw string to translate.
    """
    def __init__(self, pKey, stRaw):
        self.key = pKey;
        self.service = build('translate', 'v2', developerKey=self.key);
        self.stRaw = stRaw;
        self.length = len(stRaw); # store length
        self.tObj = [];         # dictionary object
        print_verb('stRaw: ' + stRaw)
    def execute(self, source_language, target_language):
        """Params are service object (resulting from handshake with GoogleTran
        Raw string for translation (@note no comment lines/special symbols?)

        Args:
            source_language (str): language to translate from.
            target_language (str): language to translate to.
        """
        # translate object.
        self.tObj = self.service.translations().list(
                    source=source_language,
                    target=target_language,
                    q=[self.stRaw]
                    ).execute()
        return self.tObj


class HandleSettings(sublime_plugin.ApplicationCommand):
    """Returns settings object for manipulation/reference"""
    def __init__(self, arg):
        self.values = sublime.load_settings(arg)
