import operator     # required for sorting algorithm.
import threading    # required for generating thread per comment.
import sys          # required for argument handling at command line.
import json         # required for API key read
import codecs       # required for fixing Unicode issues when reading certain files.
import argparse     # ARgument parser module, simplifies line arguments.

from subprocess import call         # for clear
from googleapiclient.discovery import build         # required for google api access

__author__      = 'dev.scw@gmail.com'
__devKey__      = json.load(open('key.json'))['tran_key']
__version__     = '2.0.3'


""" Special symbols array contains characters or symbols that, if found in a comment line,
will be considered as 'commented out code', and will NOT be parsed through translation
tool. This is to avoid parsing large commented out blocks found in code.
"""
special_symbols = [';', 'unsigned int', 'unsigned char', '()']

# parse command line arguments.
ap = argparse.ArgumentParser()
ap.add_argument("-t", "--trans", required=True,
    help="Name of file to translate")
ap.add_argument("-nt", "--thread", default=False,
    action='store_true',
    required=False,
    help="Add -nt to run non-threaded version")
ap.add_argument("-s", "--source", default='it',
    help="Set source language")
ap.add_argument("-d", "--destination", default='en',
    help="Set destination language")

args = vars(ap.parse_args())
print(args)
# check if running in threaded mode (@note threaded mode has some issues on linux
# due to file open requests)
run_threaded = True
if args['thread'] == True:
    print('Running un-threaded.')
    run_threaded = False

file_name = args['trans']
source_language = args['source']
target_language = args['destination']


class GoogleTran(object):
    """Returns object for translation.

    An object is created each time a translation request is desired in order
    to allow safe threading with the google API.
    """
    def __init__(self, pKey, stRaw):
        self.key        = pKey
        self.service    = build('translate', 'v2', developerKey=self.key)
        self.stRaw      = stRaw
        self.tObj       = []         # dictionary object

    def execute(self):
        """Params are service object (resulting from handshake with GoogleTran
        Raw string for translation (special symbols removed)
        """
        global target_language
        global source_language
        # translate object.
        self.tObj = self.service.translations().list(
                    source=source_language,
                    target=target_language,
                    q=[self.stRaw]
                    ).execute()
        return self.tObj

class LineObject(object):
    """Object for storing line contents, line number, position of comment."""
    def __init__(self, line_num, str, idx):
        self.number = line_num
        self.string = str
        self.idx    = idx

def string_is_not_code(line):
    """Searches parameter string for signs of code.
    
    Used to check if comment is actually removed code rather than real comment.

    Args:
        special_symbols (str array): global declared at top of source file, contains
            all symbols for commented out code detection function.
    """
    global special_symbols
    ret = True
    # on creation of line object, search object for common code characters inside
    # code block that may indicate commented out code.
    for idx in range(len(special_symbols)):
        if line.find(special_symbols[idx]) != -1:
            # suspect character found
            ret = False
    return ret

class ApiThreadCall(threading.Thread):
    """Class for managing threaded translate. 

    As advised by https://developers.google.com/api-client-library/python/guide/thread_safety
    Threading is easily achieved by creating a new object. This is because the Google API
    requests are not thread safe!!!!
    Thread execution is delcared in run() member function, thread.start() is required
    to call execute of translation object.

    Args:
        tran_obj (Class GoogleTran): object contains string and build request for googleapiclient.
        line_num (int): line number of comment read from file.
    """
    def __init__(self, tran_obj, lin_num, timeout=5):
        self.timeout    = timeout;
        self.line_num   = lin_num;
        self.tran       = tran_obj;
        self.result     = None;
        threading.Thread.__init__(self);
    def run(self):
        self.result = self.tran.execute()
        return

class NoThreadCall(object):
    """Class for managing un-threaded translate. 

    Use this object when emulating threaded system without creating thread requests.
    This method is often used for large files on linux distrbutions as it is more stable
    due to less file pointers being created

    Args:
        string (str): string resulted from translate.
        lin_num (int): line number of comment read from file.
    """
    def __init__(self, string, lin_num):
        self.result      = string;
        self.line_num    = lin_num;


def handle_threads(threads):
    """Loops through threads, execute handshake and append.

    Args:
        threads (thread array): all thread requests to be serviced.
    """
    print('Handling all threads...')
    temp_threads = threads
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


def strip_comment(line, location):
    """@note this could probably be encapsulated better.
    Rip out comment returns 'NOT_COM' if no comment found.

    Args:
        line (str): comment found in line.
        location (int): location of comment found in line - start address.
    """
    ret_val = 'NOT_COM'
    if location != -1:
        ret_val = line[(location + 2):]
    return ret_val


class ProgressBar(object):
    """Displays progress bar while translation is occurring. 

    Provides line number over number of lines inside file for parsing.

    Args:
        file_size (int): file size read from entire file.
    """
    def __init__(self, file_size, size=30, symbol='=', prog='%', space=''):
        self.size = size;
        self.symbol = symbol;
        self.mod = 0;
        self.file_size = file_size;
        self.state = '/'
        self.prog = prog;
        self.space = space;
    def display(self, line_number):
        progress = ((line_number * self.size)/self.file_size)
        self.prog = ('=' * int(progress))
        self.space = (' ' * (self.size-int(progress) - 1))
        if line_number % 20:
            if self.state == '/':
                self.state = '\\'
            else:
                self.state = '/'
        print('\r :' + self.state + ' Progress [' + self.prog + self.space + ']'  + ' Line: ' + str(line_num) + '/' + str(self.file_size), end='')
    def clean(self):
        """Call after ProgressBar to update terminal pointer"""
        print("")


"""
Script execution is below:
    Threaded execution:
        1. Validate file name and calculate size (used for progress bar).
        2. Print execution strings / Generate progress bar on screen.
        3. Read file with codec formatting specified (issues on Linux system reading Windows format line endings)
        4. Generate new file with same name + _trans appended.
        5. For every line in file, read line, create LineObject. If comment found, store comment location as idx for
            reconstruction. Create thread and start thread for every valid comment found.
        6. Handle all threads.
        7. Process all translations from non-active threads.
        8. Close files, exit().
"""
if __name__ == '__main__':
    print('Starting translation of"{}"'.format(file_name))

    ## Input file
    try:
        input_ptr = codecs.open(file_name, 'r', encoding='ISO-8859-1')
    except FileNotFoundError:
        print('File name invalid.')
        exit()

    for file_size, l in enumerate(input_ptr):
        pass

    # @note fix for bug where if file is temporary file or has no contents (blank),
    # file_size will causes program to crash. We try/except on file_size here to make sure it is valid.
    try:
        file_size
    except NameError:
        print('File size generation has failed, likely temporary file or naming issue.')
        exit()

    progress = ProgressBar(file_size+1)

    input_ptr.seek(0) # resets file pointer back to start.

    # build files for storing output (parsed) and output (converted)
    out_ptr = codecs.open(file_name[:file_name.find('.')] + '.txt', 'w', 'utf-8')
    new_file_ptr = codecs.open(file_name[:file_name.find('.')] + '_trans.' + file_name[file_name.find('.') + 1:], 'w', 'utf-8')


    line_num = 0

    # Store file info and threads.
    new_file = []
    threads = []

    # strip comments and store in object list
    for idx, line in enumerate(input_ptr):
        line_num+=1

        ## append every line read from file.
        new_file.append(LineObject((idx + 1), line, 0))
        # If comment found, start translation thread.
        comment_loc = line.find('//')
        comment = strip_comment(line, comment_loc)
        # Skip if we suspect string is commented out code and not a true comment.
        if comment != 'NOT_COM' and string_is_not_code(comment):
            if run_threaded == True:
                # create thread for each obj.
                thread = ApiThreadCall(GoogleTran(__devKey__, comment), (idx + 1))       # obj, line_num for reconstrcution
                # @note unsure why we stored this dx? it's never used? @bug
                new_file[(idx)].idx = comment_loc       # store comment index for reconstruction.
                threads.append(thread)
                thread.start()
            else: # un-threaded mode, more stable for linux virtual env distributions.
                new_file[(idx)].idx = comment_loc       # store comment index for reconstruction.
                tran = GoogleTran(__devKey__, comment)
                # force translation start.
                threads.append(NoThreadCall(tran.execute(), idx + 1))
        progress.display(idx + 1)

    # Cleans up display pointer for further messages.
    progress.clean()

    if run_threaded == True:
        # Process all threads.
        handle_threads(threads)
    # else we've already handled all requests.

    thread_idx = 0
    # Construct file
    for line_num in range(len(new_file)):
        line = new_file[line_num].string         # read raw line from stored memory.
        #line_num = x+1
        ## Handles post process of lines after translation, checks if translation was requested
        ## and if so process line accordingly.
        if len(threads):
            if threads[thread_idx].line_num == (line_num + 1):
                line = LineObject(line_num, line[:new_file[line_num].idx] + '//' + threads[thread_idx].result['translations'][0]['translatedText'] + '\n', new_file[line_num].idx).string
                thread_idx+=1
                if thread_idx == len(threads):
                    thread_idx = 0       #reset to prevent out of range indexing on threads.
        new_file_ptr.write(line)     
        out_ptr.write('{}  ## line: {}\n'.format(line, str(line_num + 1)))      # write out to txt file with list of translations created
    # cleanup
    new_file_ptr.close()
    input_ptr.close()
    out_ptr.close()
