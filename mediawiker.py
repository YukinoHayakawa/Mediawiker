#!/usr/bin/env python\n
# -*- coding: utf-8 -*-

import sys
pythonver = sys.version_info[0]

if pythonver >= 3:
    from . import mwclient
else:
    import mwclient
import webbrowser
import urllib
from os.path import splitext, basename
from re import sub
import sublime
import sublime_plugin
#https://github.com/wbond/sublime_package_control/wiki/Sublime-Text-3-Compatible-Packages
#http://www.sublimetext.com/docs/2/api_reference.html
#http://www.sublimetext.com/docs/3/api_reference.html
#sublime.message_dialog


def mw_get_setting(key, default_value=None):
    settings = sublime.load_settings('Mediawiker.sublime-settings')
    return settings.get(key, default_value)


def mw_set_setting(key, value):
    settings = sublime.load_settings('Mediawiker.sublime-settings')
    settings.set(key, value)
    sublime.save_settings('Mediawiker.sublime-settings')


def mw_get_connect(password=''):
    site_name_active = mw_get_setting('mediawiki_site_active')
    site_list = mw_get_setting('mediawiki_site')
    site = site_list[site_name_active]['host']
    path = site_list[site_name_active]['path']
    username = site_list[site_name_active]['username']
    domain = site_list[site_name_active]['domain']
    is_https = True if 'https' in site_list[site_name_active] and site_list[site_name_active]['https'] else False
    if is_https:
        sublime.status_message('Trying to get https connection to https://%s' % site)
    addr = site if not is_https else ('https', site)
    sitecon = mwclient.Site(addr, path)
    # if login is not empty - auth required
    if username:
        try:
            sitecon.login(username=username, password=password, domain=domain)
            sublime.status_message('Logon successfully.')
        except mwclient.LoginError as e:
            sublime.status_message('Login failed: %s' % e[1]['result'])
            return
    else:
        sublime.status_message('Connection without authorization')
    return sitecon


def mw_strunquote(string_value):
    if pythonver >= 3:
        return urllib.parse.unquote(string_value)
    else:
        return urllib.unquote(string_value.encode('ascii')).decode('utf-8')


def mw_strquote(string_value):
    if pythonver >= 3:
        return urllib.parse.quote(string_value)
    else:
        return urllib.quote(string_value.encode('utf-8'))


def mw_pagename_clear(pagename):
    """ Return clear pagename if page-url was set instead of.."""
    site_name_active = mw_get_setting('mediawiki_site_active')
    site_list = mw_get_setting('mediawiki_site')
    site = site_list[site_name_active]['host']
    pagepath = site_list[site_name_active]['pagepath']
    try:
        pagename = mw_strunquote(pagename)
    except UnicodeEncodeError:
        return pagename
    except Exception:
        return pagename

    if site in pagename:
        pagename = sub(r'(https?://)?%s%s' % (site, pagepath), '', pagename)

    sublime.status_message('Page name was cleared.')
    return pagename


def mw_save_mypages(title):
    #for wiki '_' and ' ' are equal in page name
    title = title.replace('_', ' ')
    pagelist_maxsize = mw_get_setting('mediawiker_pagelist_maxsize')
    site_name_active = mw_get_setting('mediawiki_site_active')
    mediawiker_pagelist = mw_get_setting('mediawiker_pagelist', {})

    if site_name_active not in mediawiker_pagelist:
        mediawiker_pagelist[site_name_active] = []

    my_pages = mediawiker_pagelist[site_name_active]

    if my_pages:
        while len(my_pages) >= pagelist_maxsize:
            my_pages.pop(0)

        if title in my_pages:
            #for sorting
            my_pages.remove(title)
    my_pages.append(title)
    mw_set_setting('mediawiker_pagelist', mediawiker_pagelist)


def mw_get_title(view_name, file_name):
    ''' returns page title from view_name or from file_name'''

    if view_name:
        return view_name
    elif file_name:
        wiki_extensions = mw_get_setting('mediawiker_files_extension')
        #haven't view.name, try to get from view.file_name (without extension)
        title, ext = splitext(basename(file_name))
        if ext[1:] in wiki_extensions and title:
            return title
        else:
            sublime.status_message('Anauthorized file extension for mediawiki publishing. Check your configuration for correct extensions.')
            return ''
    else:
        return ''


def mw_get_hlevel(header_string, substring):
    return int(header_string.count(substring) / 2)


class MediawikerInsertTextCommand(sublime_plugin.TextCommand):

    def run(self, edit, position, text):
        self.view.insert(edit, position, text)


class MediawikerPageCommand(sublime_plugin.WindowCommand):
    '''prepare all actions with wiki'''

    action = ''
    inputpanel = None
    is_inputfixed = False
    run_in_new_window = False

    def run(self, action, title=''):
        self.action = action

        if self.action == 'mediawiker_show_page':
            if mw_get_setting('mediawiker_newtab_ongetpage'):
                self.run_in_new_window = True

            if not title:
                pagename_default = ''
                #use clipboard or selected text for page name
                if bool(mw_get_setting('mediawiker_clipboard_as_defaultpagename')):
                    pagename_default = sublime.get_clipboard().strip()
                if not pagename_default:
                    selection = self.window.active_view().sel()
                    for selreg in selection:
                        pagename_default = self.window.active_view().substr(selreg).strip()
                        break
                self.inputpanel = self.window.show_input_panel('Wiki page name:', mw_pagename_clear(pagename_default), self.on_done, self.on_change, self.on_escape)
            else:
                self.on_done(title)
        elif self.action == 'mediawiker_reopen_page':
            #get page name
            title = mw_get_title(self.window.active_view().name(), self.window.active_view().file_name())
            #Note: reopen on the current tab, not new
            self.action = 'mediawiker_show_page'
            self.on_done(title)
        elif self.action == 'mediawiker_publish_page':
            #publish current page to wiki server
            self.on_done('')
        elif self.action == 'mediawiker_add_category':
            #add category to current page
            self.on_done('')

    def on_escape(self):
        self.inputpanel = None

    def on_change(self, text):
        #hack.. now can't to edit input_panel text.. try to reopen panel with cleared pagename :(
        pagename_cleared = mw_pagename_clear(text)
        if text != pagename_cleared:
            self.inputpanel = self.window.show_input_panel('Wiki page name:', pagename_cleared, self.on_done, self.on_change, self.on_escape)

    def on_done(self, text):
        if self.run_in_new_window:
            sublime.active_window().new_file()
            self.run_in_new_window = False
        try:
            text = mw_pagename_clear(text)
            self.window.run_command("mediawiker_validate_connection_params", {"title": text, "action": self.action})
        except ValueError as e:
            sublime.message_dialog(e)


class MediawikerOpenPageCommand(sublime_plugin.WindowCommand):
    ''' alias to Get page command '''

    def run(self):
        self.window.run_command("mediawiker_page", {"action": "mediawiker_show_page"})


class MediawikerReopenPageCommand(sublime_plugin.WindowCommand):
    ''' alias to Reopen page command '''

    def run(self):
        self.window.run_command("mediawiker_page", {"action": "mediawiker_reopen_page"})


class MediawikerPostPageCommand(sublime_plugin.WindowCommand):
    ''' alias to Publish page command '''

    def run(self):
        self.window.run_command("mediawiker_page", {"action": "mediawiker_publish_page"})


class MediawikerSetCategoryCommand(sublime_plugin.WindowCommand):
    ''' alias to Add category command '''

    def run(self):
        self.window.run_command("mediawiker_page", {"action": "mediawiker_add_category"})


class MediawikerPageListCommand(sublime_plugin.WindowCommand):
    my_pages = []

    def run(self):
        site_name_active = mw_get_setting('mediawiki_site_active')
        mediawiker_pagelist = mw_get_setting('mediawiker_pagelist', {})
        self.my_pages = mediawiker_pagelist[site_name_active] if site_name_active in mediawiker_pagelist else []
        if self.my_pages:
            self.my_pages.reverse()
            #self.window.show_quick_panel(self.my_pages, self.on_done)
            #error 'Quick panel unavailable' fix with timeout..
            sublime.set_timeout(lambda: self.window.show_quick_panel(self.my_pages, self.on_done), 1)
        else:
            sublime.status_message('List of pages for wiki "%s" is empty.' % (site_name_active))

    def on_done(self, index):
        if index >= 0:
            # escape from quick panel return -1
            text = self.my_pages[index]
            try:
                self.window.run_command("mediawiker_page", {"title": text, "action": "mediawiker_show_page"})
            except ValueError as e:
                sublime.message_dialog(e)


class MediawikerValidateConnectionParamsCommand(sublime_plugin.WindowCommand):
    site = None
    password = ''
    title = ''
    action = ''

    def run(self, title, action):
        self.action = action  # TODO: check for better variant
        self.title = title
        site = mw_get_setting('mediawiki_site_active')
        site_list = mw_get_setting('mediawiki_site')
        self.password = site_list[site]["password"]
        if site_list[site]["username"]:
            #auth required if username exists in settings
            if not self.password:
                #need to ask for password
                self.window.show_input_panel('Password:', '', self.on_done, None, None)
            else:
                self.call_page()
        else:
            #auth is not required
            self.call_page()

    def on_done(self, password):
        self.password = password
        self.call_page()

    def call_page(self):
        self.window.active_view().run_command(self.action, {"title": self.title, "password": self.password})


class MediawikerShowPageCommand(sublime_plugin.TextCommand):
    def run(self, edit, title, password):
        is_page_editable = False
        denied_message = 'You have not rights to edit this page. Click OK button to view its source.'
        sitecon = mw_get_connect(password)
        page = sitecon.Pages[title]
        is_page_editable = True if page.can('edit') else sublime.ok_cancel_dialog(denied_message)
        if is_page_editable:
            text = page.edit()
            if not text:
                sublime.status_message('Wiki page %s is not exists. You can create new..' % (title))
                text = '<New wiki page: Remove this with text of the new page>'
            self.view.erase(edit, sublime.Region(0, self.view.size()))
            self.view.set_syntax_file('Packages/Mediawiker/Mediawiki.tmLanguage')
            self.view.set_name(title)
            self.view.run_command('mediawiker_insert_text', {'position': 0, 'text': text})
            sublime.status_message('Page %s was opened successfully.' % (title))
        else:
            sublime.status_message('You have not rights to edit this page')


class MediawikerPublishPageCommand(sublime_plugin.TextCommand):
    my_pages = None
    page = None
    title = ''
    current_text = ''

    def run(self, edit, title, password):
        sitecon = mw_get_connect(password)
        self.title = mw_get_title(self.view.name(), self.view.file_name())
        if self.title:
            self.page = sitecon.Pages[self.title]
            if self.page.can('edit'):
                self.current_text = self.view.substr(sublime.Region(0, self.view.size()))
                summary_message = 'Changes summary (%s):' % mw_get_setting('mediawiki_site_active')
                self.view.window().show_input_panel(summary_message, '', self.on_done, None, None)
            else:
                sublime.status_message('You have not rights to edit this page')
        else:
            sublime.status_message('Can\'t publish page with empty title')
            return

    def on_done(self, summary):
        try:
            summary = '%s%s' % (summary, mw_get_setting('mediawiker_summary_postfix', ' (by SublimeText.Mediawiker)'))
            mark_as_minor = mw_get_setting('mediawiker_mark_as_minor')
            if self.page.can('edit'):
                #invert minor settings command '!'
                if summary[0] == '!':
                    mark_as_minor = not mark_as_minor
                    summary = summary[1:]
                self.page.save(self.current_text, summary=summary.strip(), minor=mark_as_minor)
            else:
                sublime.status_message('You have not rights to edit this page')
        except mwclient.EditError as e:
            sublime.status_message('Can\'t publish page %s (%s)' % (self.title, e))
        sublime.status_message('Wiki page %s was successfully published to wiki.' % (self.title))
        #save my pages
        mw_save_mypages(self.title)


class MediawikerShowTocCommand(sublime_plugin.TextCommand):
    items = []
    regions = []

    def run(self, edit):
        self.items = []
        self.regions = []
        pattern = '^={1,5}(.*)?={1,5}'
        self.regions = self.view.find_all(pattern)
        for r in self.regions:
            item = self.view.substr(r).strip(' \t').rstrip('=').replace('=', '  ')
            self.items.append(item)
        sublime.set_timeout(lambda: self.view.window().show_quick_panel(self.items, self.on_done), 1)

    def on_done(self, index):
        if index >= 0:
            # escape from quick panel return -1
            self.view.show(self.regions[index])
            self.view.sel().clear()
            self.view.sel().add(self.regions[index])


class MediawikerEnumerateTocCommand(sublime_plugin.TextCommand):
    items = []
    regions = []

    def run(self, edit):
        self.items = []
        self.regions = []
        pattern = '^={1,5}(.*)?={1,5}'
        self.regions = self.view.find_all(pattern)
        header_level_number = [0, 0, 0, 0, 0]
        len_delta = 0
        for r in self.regions:
            if len_delta:
                #prev. header text was changed, move region to new position
                r_new = sublime.Region(r.a + len_delta, r.b + len_delta)
            else:
                r_new = r
            region_len = r_new.b - r_new.a
            header_text = self.view.substr(r_new)
            level = mw_get_hlevel(header_text, "=")
            current_number_str = ''
            i = 1
            #generate number value, start from 1
            while i <= level:
                position_index = i - 1
                header_number = header_level_number[position_index]
                if i == level:
                    #incr. number
                    header_number += 1
                    #save current number
                    header_level_number[position_index] = header_number
                    #reset sub-levels numbers
                    header_level_number[i:] = [0] * len(header_level_number[i:])
                if header_number:
                    current_number_str = "%s.%s" % (current_number_str, header_number) if current_number_str else '%s' % (header_number)
                #incr. level
                i += 1

            #get title only
            header_text_clear = header_text.strip(' =\t')
            header_text_clear = sub(r'^(\d\.)+\s+(.*)', r'\2', header_text_clear)
            header_tag = '=' * level
            header_text_numbered = '%s %s. %s %s' % (header_tag, current_number_str, header_text_clear, header_tag)
            len_delta += len(header_text_numbered) - region_len
            self.view.replace(edit, r_new, header_text_numbered)


class MediawikerSetActiveSiteCommand(sublime_plugin.WindowCommand):
    site_keys = []
    site_on = '>'
    site_off = ' ' * 3

    def run(self):
        site_active = mw_get_setting('mediawiki_site_active')
        sites = mw_get_setting('mediawiki_site')
        self.site_keys = list(sites.keys())
        for key in self.site_keys:
            checked = self.site_on if key == site_active else self.site_off
            self.site_keys[self.site_keys.index(key)] = '%s %s' % (checked, key)
        sublime.set_timeout(lambda: self.window.show_quick_panel(self.site_keys, self.on_done), 1)

    def on_done(self, index):
        # not escaped and not active
        if index >= 0 and self.site_on != self.site_keys[index][:len(self.site_on)]:
            mw_set_setting("mediawiki_site_active", self.site_keys[index].strip())


class MediawikerOpenPageInBrowserCommand(sublime_plugin.WindowCommand):
    def run(self):
        site_name_active = mw_get_setting('mediawiki_site_active')
        site_list = mw_get_setting('mediawiki_site')
        site = site_list[site_name_active]["host"]
        pagepath = site_list[site_name_active]["pagepath"]
        title = mw_get_title(self.window.active_view().name(), self.window.active_view().file_name())
        if title:
            webbrowser.open('http://%s%s%s' % (site, pagepath, title))
        else:
            sublime.status_message('Can\'t open page with empty title')
            return


class MediawikerAddCategoryCommand(sublime_plugin.TextCommand):
    categories_list = None
    password = ''
    title = ''
    CATEGORY_NAMESPACE = 14  # category namespace number

    def run(self, edit, title, password):
        sitecon = mw_get_connect(self.password)
        category_root = mw_get_setting('mediawiker_category_root')
        category = sitecon.Pages[category_root]
        self.categories_list_names = []
        self.categories_list_values = []

        for page in category:
            if page.namespace == self.CATEGORY_NAMESPACE:
                self.categories_list_values.append(page.name)
                self.categories_list_names.append(page.name[page.name.find(':') + 1:])
        sublime.set_timeout(lambda: sublime.active_window().show_quick_panel(self.categories_list_names, self.on_done), 1)

    def on_done(self, idx):
        # the dialog was cancelled
        if idx is -1:
            return
        index_of_textend = self.view.size()
        self.view.run_command('mediawiker_insert_text', {'position': index_of_textend, 'text': '[[%s]]' % self.categories_list_values[idx]})


class MediawikerCsvTableCommand(sublime_plugin.TextCommand):
    ''' selected text, csv data to wiki table '''
    #TODO: rewrite as simple to wiki command
    def run(self, edit):
        delimiter = mw_get_setting('mediawiker_csvtable_delimiter', '|')
        table_header = '{|'
        table_footer = '|}'
        table_properties = ' '.join(['%s="%s"' % (prop, value) for prop, value in mw_get_setting('mediawiker_wikitable_properties', {}).items()])
        cell_properties = ' '.join(['%s="%s"' % (prop, value) for prop, value in mw_get_setting('mediawiker_wikitable_cell_properties', {}).items()])
        if cell_properties:
            cell_properties = ' %s | ' % cell_properties

        selected_regions = self.view.sel()
        for reg in selected_regions:
            table_data_dic_tmp = []
            table_data = ''
            for line in self.view.substr(reg).split('\n'):
                if delimiter in line:
                    row = line.split(delimiter)
                    table_data_dic_tmp.append(row)

            #verify and fix columns count in rows
            cols_cnt = len(max(table_data_dic_tmp, key=len))
            for row in table_data_dic_tmp:
                len_diff = cols_cnt - len(row)
                while len_diff:
                    row.append('')
                    len_diff -= 1

            for row in table_data_dic_tmp:
                if table_data:
                    table_data += '\n|-\n'
                    column_separator = '||'
                else:
                    table_data += '|-\n'
                    column_separator = '!!'
                for col in row:
                    col_sep = column_separator if row.index(col) else column_separator[0]
                    table_data += '%s%s%s ' % (col_sep, cell_properties, col)

            self.view.replace(edit, reg, '%s %s\n%s\n%s' % (table_header, table_properties, table_data, table_footer))


class MediawikerEditPanelCommand(sublime_plugin.WindowCommand):
    options = []

    def run(self):
        snippet_tag = u'\u24C8'
        self.options = mw_get_setting('mediawiker_panel', {})
        if self.options:
            office_panel_list = ['\t%s' % val['caption'] if val['type'] != 'snippet' else '\t%s %s' % (snippet_tag, val['caption']) for val in self.options]
            self.window.show_quick_panel(office_panel_list, self.on_done)

    def on_done(self, index):
        if index >= 0:
            # escape from quick panel return -1
            try:
                action_type = self.options[index]['type']
                action_value = self.options[index]['value']
                if action_type == 'snippet':
                    #run snippet
                    self.window.active_view().run_command("insert_snippet", {"name": action_value})
                elif action_type == 'window_command':
                    #run command
                    self.window.run_command(action_value)
                elif action_type == 'text_command':
                    #run command
                    self.window.active_view().run_command(action_value)
            except ValueError as e:
                sublime.status_message(e)


class MediawikerTableWikiToSimpleCommand(sublime_plugin.TextCommand):
    ''' convert selected (or under cursor) wiki table to Simple table (TableEdit plugin) '''

    #TODO: wiki table properties will be lost now...
    def run(self, edit):
        selection = self.view.sel()
        table_region = None

        if not self.view.substr(selection[0]):
            table_region = self.gettable()
        else:
            for reg in selection:
                table_region = reg
                break  # only first region will be proceed..

        if table_region:
            text = self.tblfixer(self.view.substr(table_region))
            table_data = self.table_parser(text)
            self.view.replace(edit, table_region, self.drawtable(table_data))
            #Turn on TableEditor
            try:
                self.view.run_command('table_editor_enable_for_current_view', {'prop': 'enable_table_editor'})
            except Exception as e:
                sublime.status_message('Need to correct install plugin TableEditor: %s' % e)

    def table_parser(self, text):
        is_table = False
        is_row = False
        TBL_START = '{|'
        TBL_STOP = '|}'
        TBL_ROW_START = '|-'
        CELL_FIRST_DELIM = '|'
        CELL_DELIM = '||'
        #CELL_HEAD_FIRST_DELIM = '!'
        CELL_HEAD_DELIM = '!!'
        CELL_FIRST_DELIM = '|'
        is_table_has_header = False
        table_data = []

        for line in text.split('\n'):
            is_header = False
            line = line.replace('\n', '')
            if line[:2] == TBL_START:
                is_table = True
            if line[:2] == TBL_STOP:
                is_table = False
            if line[:2] == TBL_ROW_START:
                is_row = True
            if is_table and is_row and line[:2] != TBL_ROW_START:
                row_data = []
                line = self.delim_fixer(line)  # temp replace char | in cell properties to """"
                if CELL_DELIM in line:
                    cells = line.split(CELL_DELIM)
                elif CELL_HEAD_DELIM in line:
                    cells = line.split(CELL_HEAD_DELIM)
                    is_table_has_header = True
                for cell in cells:
                    if CELL_FIRST_DELIM in cell:
                        #cell properties exists
                        try:
                            props_data, cell_data = [val.strip() for val in cell.split(CELL_FIRST_DELIM)]
                            props_data = props_data.replace('""""', CELL_FIRST_DELIM)
                        except Exception as e:
                            print('Incorrect cell! %s' % e)
                    else:
                        props_data, cell_data = '', cell.strip()

                    if is_table_has_header:
                        is_header = True
                        is_table_has_header = False
                    #saving cell properties, but not used now..
                    row_data.append({'properties': props_data, 'cell_data': cell_data, 'is_header': is_header})
                table_data.append(row_data)
        return table_data

    def gettable(self):
        cursor_position = self.view.sel()[0].begin()
        pattern = r'^\{\|(.*\n)*?\|\}'
        regions = self.view.find_all(pattern)
        for reg in regions:
            if reg.a <= cursor_position <= reg.b:
                return reg

    def drawtable(self, table_list):
        '''Draw table as Table editor: Simple table'''
        if not table_list:
            return ''
        text = ''
        need_header = table_list[0][0]['is_header']
        for row in table_list:
            header_line = ''
            if need_header:
                header_line = '|-\n'
                need_header = False  # draw header only first time
            text += '| '
            text += ' | '.join(cell['cell_data'] for cell in row)
            text += ' |\n%s' % header_line
        return text

    def tblfixer(self, text):
        text = sub(r'(.){1}(\|\-)', r'\1\n\2', text)  # |- on the same line as {| - move to next line
        text = sub(r'(\{\|.*\n)([\|\!]\s?[^-])', r'\1|-\n\2', text)  # if |- skipped after {| line, add it
        text = sub(r'\n(\|\s)', r'|| ', text)  # columns to one line
        text = sub(r'(\|\-)(.*?)(\|\|)', r'\1\2\n| ', text)  # |- on it's own line
        return text

    def delim_fixer(self, string_data):
        string_data = string_data[1:]
        tags_start = ['[', '{']
        tags_end = [']', '}']
        CELL_CHAR = '|'
        REPLACE_STR = '""""'
        is_tag = False
        string_out = ''
        for char in string_data:
            if char in tags_start and not is_tag:
                is_tag = True
            if is_tag and char in tags_end:
                is_tag = False
            if is_tag and char == CELL_CHAR:
                string_out += REPLACE_STR
            else:
                string_out += char
        return string_out


class MediawikerTableSimpleToWikiCommand(sublime_plugin.TextCommand):
    ''' convert selected (or under cursor) Simple table (TableEditor plugin) to wiki table '''
    def run(self, edit):
        selection = self.view.sel()
        table_region = None
        if not self.view.substr(selection[0]):
            table_region = self.gettable()
        else:
            for reg in selection:
                table_region = reg
                break  # only first region will be proceed..

        if table_region:
            text = self.view.substr(table_region)
            table_data = self.table_parser(text)
            self.view.replace(edit, table_region, self.drawtable(table_data))

    def table_parser(self, text):
        table_data = []
        TBL_HEADER_STRING = '|-'
        need_header = False
        if text.split('\n')[1][:2] == TBL_HEADER_STRING:
            need_header = True
        for line in text.split('\n'):
            if line:
                row_data = []
                if line[:2] == TBL_HEADER_STRING:
                    continue
                elif line[0] == '|':
                    cells = line[1:-1].split('|')  # without first and last char "|"
                    for cell_data in cells:
                        row_data.append({'properties': '', 'cell_data': cell_data, 'is_header': need_header})
                    if need_header:
                        need_header = False
            if row_data and type(row_data) is list:
                table_data.append(row_data)
        return table_data

    def gettable(self):
        cursor_position = self.view.sel()[0].begin()
        # ^([^\|\n].*)?\n\|(.*\n)*?\|.*\n[^\|] - all tables regexp (simple and wiki)?
        pattern = r'^\|(.*\n)*?\|.*\n[^\|]'
        regions = self.view.find_all(pattern)
        for reg in regions:
            if reg.a <= cursor_position <= reg.b:
                table_region = sublime.Region(reg.a, reg.b - 2)  # minus \n and [^\|]
                return table_region

    def drawtable(self, table_list):
        ''' draw wiki table '''
        TBL_START = '{|'
        TBL_STOP = '|}'
        TBL_ROW_START = '|-'
        CELL_FIRST_DELIM = '|'
        CELL_DELIM = '||'
        CELL_HEAD_FIRST_DELIM = '!'
        CELL_HEAD_DELIM = '!!'

        text_wikitable = ''
        table_properties = ' '.join(['%s="%s"' % (prop, value) for prop, value in mw_get_setting('mediawiker_wikitable_properties', {}).items()])

        need_header = table_list[0][0]['is_header']
        is_first_line = True
        for row in table_list:
            if need_header or is_first_line:
                text_wikitable += '%s\n%s' % (TBL_ROW_START, CELL_HEAD_FIRST_DELIM)
                text_wikitable += self.getrow(CELL_HEAD_DELIM, row)
                is_first_line = False
                need_header = False
            else:
                text_wikitable += '\n%s\n%s' % (TBL_ROW_START, CELL_FIRST_DELIM)
                text_wikitable += self.getrow(CELL_DELIM, row)

        return '%s %s\n%s\n%s' % (TBL_START, table_properties, text_wikitable, TBL_STOP)

    def getrow(self, delimiter, rowlist=[]):
        cell_properties = ' '.join(['%s="%s"' % (prop, value) for prop, value in mw_get_setting('mediawiker_wikitable_cell_properties', {}).items()])
        cell_properties = '%s | ' % cell_properties if cell_properties else ''
        try:
            return delimiter.join(' %s%s ' % (cell_properties, cell['cell_data'].strip()) for cell in rowlist)
        except Exception as e:
            print('Error in data: %s' % e)