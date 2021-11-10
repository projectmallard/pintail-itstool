# pintail - Build static sites from collections of Mallard documents
# Copyright (c) 2016 Shaun McCance <shaunm@gnome.org>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import shutil
import subprocess

import pintail.translation
import pintail.site

class ItstoolTranslationProvider(pintail.translation.TranslationProvider):
    """
    A translation provider using PO files with itstool.

    This translation provider assumes that, for any source, the PO files with
    translations are kept in language subdirectories of the source's parent
    directory. This works well for external repos with individual documents,
    like GNOME has. It does not work so well for simple Mallard site layouts.

    FIXME: Make this more flexible for different layouts. Nothing about itstool
    prevents this plugin from being smarter.
    """

    def __init__(self, site):
        pintail.translation.TranslationProvider.__init__(self, site)
        self._po_for_source = {}
        self._mo_for_po = {}
        self._batched_sources = {}
        self._executor = None
        self._threaded_sources = {}

    def get_directory_langs(self, directory):
        """
        Get all languages available for a single directory.

        For each source in the directory, this method looks at the subdirectories
        of the source's parent directory. If a directory contains a PO file with
        the same basename as the directory, then it creates a language with that
        basename as the language code.
        """
        langs = []
        for source in directory.sources:
            parentpath = os.path.dirname(source.get_source_path())
            for langdir in os.listdir(parentpath):
                langpath = os.path.join(parentpath, langdir)
                if os.path.isdir(langpath):
                    popath = os.path.join(langpath, langdir + '.po')
                    if os.path.isfile(popath):
                        self._po_for_source.setdefault(source, {})
                        self._po_for_source[source][langdir] = popath
                        if langdir not in langs:
                            langs.append(langdir)
        if len(langs) > 0:
            return langs
        # FIXME:
        # otherwise, if -d po, use that
        # otherwise, if directory.parent, get_directory_langs(directory.parent)
        # otherwise, return []
        return []


    def translate_directory(self, directory, lang):
        """
        Translate a directory into a language and return whether it was translated.
        """
        if self.site.config.get('itstool_thread_dirs') == 'True':
            if self._executor is None:
                import concurrent.futures
                self._executor = concurrent.futures.ThreadPoolExecutor()
            for source in directory.sources:
                def _run_source_lang(source, lang):
                    if source not in self._po_for_source:
                        return False
                    if lang not in self._po_for_source[source]:
                        return False
                    pofile = self._po_for_source[source][lang]
                    if source.name == source.directory.path:
                        pintail.site.Site._makedirs(directory.get_stage_path(lang))
                        mofile = os.path.join(directory.get_stage_path(lang), lang + '.mo')
                    else:
                        # If it's not the primary source, make a subdirectory for
                        # the mo file so we don't conflict.
                        modir = os.path.join(directory.get_stage_path(lang),
                                             source.name.replace('/', '!'))
                        pintail.site.Site._makedirs(modir)
                        mofile = os.path.join(modir, lang + '.mo')
                    subprocess.call(['msgfmt', '-o', mofile, pofile])
                    self._mo_for_po[pofile] = mofile
                    cmd = ['itstool',
                           '--path', source.get_source_path(),
                           '-m', mofile, '-l', lang,
                           '-o', directory.get_stage_path(lang)]
                    cmd += [p.get_stage_path() for p in source.pages]
                    self.site.log('TRANS', lang + ' ' + source.name)
                    ret = subprocess.call(cmd)
                    if ret != 0:
                        self.site.logger.warn('Could not translate %s to %s' % (directory.path, lang))
                        return False
                    return True
                self._threaded_sources.setdefault(source, {})
                self._threaded_sources[source][lang] = self._executor.submit(_run_source_lang, source, lang)
            return True
        return False


    def translate_page(self, page, lang):
        """
        Translate a page into a language and return whether it was translated.
        """
        if page.source not in self._po_for_source:
            return False
        if lang not in self._po_for_source[page.source]:
            return False

        if self.site.config.get('itstool_thread_dirs') == 'True':
            job = self._threaded_sources[page.source][lang]
            if job.running():
                self.site.log('WAIT', lang + ' ' + page.source.name)
            return job.result()

        pofile = self._po_for_source[page.source][lang]
        if pofile not in self._mo_for_po:
            if page.source.name == page.source.directory.path:
                pintail.site.Site._makedirs(page.directory.get_stage_path(lang))
                mofile = os.path.join(page.directory.get_stage_path(lang), lang + '.mo')
            else:
                # If it's not the primary source, make a subdirectory for
                # the mo file so we don't conflict.
                modir = os.path.join(page.directory.get_stage_path(lang),
                                     page.source.name.replace('/', '!'))
                pintail.site.Site._makedirs(modir)
                mofile = os.path.join(modir, lang + '.mo')
            subprocess.call(['msgfmt', '-o', mofile, pofile])
            self._mo_for_po[pofile] = mofile
        mofile = self._mo_for_po[pofile]

        if self.site.config.get('itstool_batch_dirs') == 'True':
            self._batched_sources.setdefault(page.source, [])
            if lang in self._batched_sources[page.source]:
                return True
            self._batched_sources[page.source].append(lang)
            self.site.log('TRANS', lang + ' ' + page.source.name)
            cmd = ['itstool',
                   '--path', os.path.dirname(page.get_source_path()),
                   '-m', mofile, '-l', lang,
                   '-o', page.directory.get_stage_path(lang)]
            cmd += [p.get_stage_path() for p in page.source.pages]
            ret = subprocess.call(cmd)
            if ret != 0:
                self.site.logger.warn('Could not translate %s to %s' % (page.directory.path, lang))
                return False
            return True
        else:
            self.site.log('TRANS', lang + ' ' + page.site_id)
            ret = subprocess.call([
                'itstool',
                '--path', os.path.dirname(page.get_source_path()),
                '-m', mofile, '-l', lang,
                '-o', page.get_stage_path(lang),
                page.get_stage_path()
            ])
            if ret != 0:
                self.site.logger.warn('Could not translate %s to %s' % (page.site_id, lang))
                return False
            return True

    def translate_media(self, source, mediafile, lang):
        """
        Translate a media file into a language and return whether it was translated.

        This implementation looks for translated media files relative to the path
        of the PO file, regardless of whether they have a listing in the PO file.
        """
        if source not in self._po_for_source:
            return False
        if lang not in self._po_for_source[source]:
            return False
        podir = os.path.dirname(self._po_for_source[source][lang])
        mfile = os.path.join(podir, mediafile)
        try:
            target = os.path.join(source.directory.get_stage_path(lang), mediafile)
            pintail.site.Site._makedirs(os.path.dirname(target))
            shutil.copyfile(mfile, target)
        except Exception as e:
            return False
        return True
