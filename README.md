# Sublime Text - Translation Plugin

The goal of this project was to provide a simple translation tool for use when working on an internationally distributed code base in C/C++.
Often in industry, projects are handed from engineer to engineer, and quite regularly between countries. During these transitions, code can be left with stray comments (__or all comments!__) in another language, proving difficult to manage.

### What's in this repository ###

* Plugin for translating files on a line-by-line basis with Google Translate (translate.sublime-package).
	* Version [1.0.6]
* Script for translating large source files with Google Translate (translate.py).
	* Version [2.0.1]
* (Hopefully, some useful tools to save you some time)

### Setting up Python, Pip on Windows ###

* Download and install [Python](https://www.python.org/downloads/).  

### How to use the script ###

Use -t switch for file name, -s for source language code (en, es, it, etc) and -d for destination language code.  
```bash
python3 translate.py -t {file_name.c/cpp} [-s SOURCE] [-d DESTINATION]
```

Windows users:

```bash
python translate.py -t examples/ciao_mondo.c
```

The script must be run in the same folder as your key.json file and the file you're translating. You'll need to create a Google cloud account and register for an API key, then modify the key.json file:

```json
{
  "tran_key" : "add_your_key_here"
}
```

Follow [this guide](https://cloud.google.com/translate/docs/getting-started) for creating an account and generating an API key (it can get a little finicky); and [this guide](https://cloud.google.com/docs/authentication/api-keys?authuser=1&hl=en&authuser=1&visit_id=1-636683862439856814-1794048889&rd=1) for creating a translation key.


To modify default source/target languages, modify the translate.py script:
```python
ap.add_argument("-s", "--source", default='it',
    help="Set source language")
ap.add_argument("-d", "--destination", default='en',
    help="Set destination language")
```
Alternatively set as command line arguments.

#### Non-threaded version ####

The script can be run in non-threaded mode (issues have been reported on Linux distributions with threaded mode).
```
python3 translate.py -t {file_name.c/cpp} -nt
```

### How to use the plugin ###

*NOTE: PACKAGE CONTROL MUST BE INSTALLED BEFORE ATTEMPTING TO RUN PLUGIN.* Sublime Text 2 doesn't come with SSL functionality built it. Installing package control will install SSL for https functionality (required by Google API Client). Get package control here: https://packagecontrol.io/installation#st2

Download source, close Sublime Text 2, extract the python **translate.sublime-package** into your Sublime/Packages directory, re-open Sublime Text 2.

The plugin's target and source languages are configurable under settings. Make sure you use a language identifier acronym that Google Translate will recognise i.e. **'de', 'it', 'en, 'es'**.

- Full list of supported languages: https://cloud.google.com/translate/docs/languages
- *Note: currently automatic language detection is NOT supported but will be in next release.*

You'll need to modify the package settings and add your generated API key (the same key will work for both the script and the plugin, just follow the above guide).

Modify the shortcut as desired (default for Windows/Linux is [ctrl+alt+t]/[ctrl+alt+g] and OSX [cmd+alt+t]).

#### Removable Characters ####

The Translate API doesn't like handling some characters and won't process concatenated strings or function names such as **'HOLA_MI_AMIGO'**. To get past this issue, any character inside the 'special_symbols' array (stored in Translate.sublime-settings) is removed and replaced with a space character before parsing. To add or remove special characters to this list, simply append them/remove them from the json in array in the settings file.

Select some text and translate.
- *Note: Multiple cursors are supported and should be fully functional. Multi-line support however is a little bit fudged (it parses all lines as a single string and Google Translate removes all end of line characters, so the result is just a long string).*

### How do I get set up? ###

* Configuration
Create Google API account and generate API key, follow instructions list above.

* Dependencies
	- translate.py
		- Python 2.7.12 recommended.
		- install requirements with pip.
		- ```pip install -r requirements.txt```
	- translate_plugin.py
		- Sublime Text 2
	-	 Package Control Installed
			- *ST2 runs its own proprietary version of Python (version 2.6) and bundled modules. The httplib2 module bundled with
		the ST2 Python isn't able to generate HTTPS connections. Installing Package Control will resolve this (you may have to restart ST2 a couple times on prompt).*
	- Extract 'translate.sublime-package' to Sublime/packages directory (you can get here easily using Preferences -> Browse Packages in ST2) or use Package Control to install from git.

### Contribution guidelines ###

- Coding standard: Try to adhere to the Google Python Coding Style, https://google.github.io/styleguide/pyguide.html
- Install pylint (or similar)
```
pip install pylint
```
- Get linting
```
pylint translate.py
```


### Who do I talk to? ###

* author: Sean Whittaker
