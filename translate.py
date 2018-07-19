import operator     # required for sorting algorithm.
import threading        # required for generating thread per comment.
import sys      # required for argument handling at command line.
from subprocess import call         # for clear
import json         # required for API key read
from googleapiclient.discovery import build         # required for google api access
import codecs     # required for fixing Unicode issues when reading certain files.
import argparse     # ARgument parser module, simplifies line arguments.

__author__ = 'seancwhittaker@gmail.com (Sean Whittaker)'
__devKey__ = json.load(open('key.json'))['tran_key']
__version__ = '2.0.1'


file_name = ''

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
    print('Running un-threaded..')
    run_threaded = False

# Set file name to argument (@note  error thrown if no argument specified, exits safely)
file_name = args['trans']
source_language = args['source']
target_language = args['destination']

""" Class and function declarations.
"""

class GoogleTran():
    """Returns object for translation.
    An object is created each time a translation request is desired in order
    to allow safe threading with the google API.
    """
    def __init__(self, pKey, stRaw):
        self.key = pKey;
        self.service = build('translate', 'v2', developerKey = self.key);
        self.stRaw = stRaw;
        self.tObj = [];         # dictionary object
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

class LineObject():
    """Object for storing line contents, line number, position of comment."""
    def __init__(self, line_num, str, idx):
        self.number = line_num;
        self.string = str;
        self.idx = idx;

def stringIsNotCode(line):
    """Searchs parameter string for signs of code, used to check if comment is
    actually removed code rather than real comment.

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
    """As advised by https://developers.google.com/api-client-library/python/guide/thread_safety
    Threading is easily achieved by creating a new object. This is because the Google API
    requests are not thread safe!!!!
    Thread execution is delcared in run() member function, thread.start() is required
    to call execute of translation object.

    Args:
        tran_obj (Class GoogleTran): object contains string and build request for googleapiclient.
        line_num (int): line number of comment read from file.
    """
    def __init__(self, tran_obj, lin_num, timeout=5):
        self.timeout = timeout;
        self.lineNum = lin_num;
        self.tran = tran_obj;
        self.result = None;
        threading.Thread.__init__(self);
    def run(self):
        self.result = self.tran.execute()
        return

class NoThreadCall():
    """Use this object when emulating threaded system without creating thread requests.
    This method is often used for large files on linux distrbutions as it is more stable
    due to less file pointers being created

    Args:
        string (str): string resulted from translate.
        lin_num (int): line number of comment read from file.
    """
    def __init__(self, string, lin_num):
        self.result = string;
        self.lineNum = lin_num;


def handleThreads(threads):
    """loop through threads, execute handshake and append.

    Args:
        threads (thread array): all thread requests to be serviced.
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


def stripCom(line, location):
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


class ProgressBar():
    """Displays progress bar while translation is occurring, provides line number
    over number of lines inside file for parsing.

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
print('Starting translation of \'' + file_name + '\'')


## Input file
try:
    input_ptr =  codecs.open(file_name, 'r', encoding = 'ISO-8859-1')
except FileNotFoundError:
    print('File name invalid.')
    exit()

# Enumerate through lines and get total size.
for file_size, l in enumerate(input_ptr):
    pass

# @note fix for bug found by Mike Carter. If file is temporary file or has no contents (blank),
# file_size will causes program to crash. We try/except on file_size here to make sure it is valid.
try:
    file_size
except NameError:
    print('File size generation has failed, likely temporary file or naming issue.')
    exit()

progress = ProgressBar(file_size+1)

input_ptr.seek(0)       # reset file pointer back to start.

# build files for storing output (parsed) and output (converted)
out_ptr =  codecs.open(file_name[:file_name.find('.')] + '.txt', 'w', 'utf-8')
new_file_ptr =  codecs.open(file_name[:file_name.find('.')] + '_trans.' + file_name[file_name.find('.') + 1:], 'w', 'utf-8')

# easily keep track of line number
line_num = 0

# Store file info and threads.
new_file = []
threads = []

# strip comments and store in object list
for line in input_ptr:
    line_num+=1
    ## append every line read from file.
    new_file.append(LineObject(line_num, line, 0))
    # If comment found, start translation thread.
    comment_loc = line.find('//')
    comment = stripCom(line, comment_loc)
    # Skip if we suspect string is commented out code and not a true comment.
    if comment != 'NOT_COM' and stringIsNotCode(comment):
        if run_threaded == True:
            # create thread for each obj.
            thread = ApiThreadCall(GoogleTran(__devKey__, comment), line_num)       # obj, line_num for reconstrcution
            # @note unsure why we stored this dx? it's never used? @bug
            new_file[(line_num-1)].idx = comment_loc       # store comment index for reconstruction.
            threads.append(thread)
            thread.start()
        else: # un-threaded mode, more stable for linux virtual env distributions.
            new_file[(line_num-1)].idx = comment_loc       # store comment index for reconstruction.
            tran = GoogleTran(__devKey__, comment)
            # force translation start.
            threads.append(NoThreadCall(tran.execute(), line_num))
    progress.display(line_num)

# Cleans up display pointer for further messages.
progress.clean()

if run_threaded == True:
    # Process all threads.
    handleThreads(threads)
# else we've already handled all requests.

thread_idx = 0
# Construct file
for x in range(len(new_file)):
    line = new_file[x].string         # read raw line from stored memory.
    line_num = x+1
    ## Handles post process of lines after translation, checks if translation was requested
    ## and if so process line accordingly.
    # @note Mike found a bug where if no comments were actually found, script would
    # fail here. Check if length is valid before indexing into thread object.
    if len(threads) != 0:
        if threads[thread_idx].lineNum == line_num:
            line = LineObject(line_num, line[:new_file[x].idx] + '//' + threads[thread_idx].result['translations'][0]['translatedText'] + '\n', new_file[x].idx).string
            thread_idx+=1
            if thread_idx == len(threads):
                thread_idx = 0       #reset to prevent out of range indexing on threads.
    new_file_ptr.write(line)       # write out to file with translations.
    out_ptr.write(line + '  ## line: ' + str(line_num) + '\n')      # write out to txt file with list of translations created

# cleanup
new_file_ptr.close()
input_ptr.close()
out_ptr.close()