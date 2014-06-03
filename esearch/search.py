#!/usr/bin/env python
#
# This script is a replacement for `emerge search`.
# It searches an index file generated by eupdatedb
# from the portage tree.
#
# Author: David Peter <davidpeter@web.de>
#

from __future__ import print_function

from getopt import getopt, GetoptError
import sys
from os import listdir, getenv, system
from os.path import isdir, exists
import re

#sys.path.insert(0, "/usr/lib/portage/pym")
# commented out so it can run from the git checkout
#sys.path.insert(0, "/usr/lib/esearch")

try:
    from portage.output import bold, red, green, darkgreen, turquoise, blue, nocolor
    from portage import settings, pkgcmp, pkgsplit, portdb, best
    from portage.util import cmp_sort_key
except ImportError:
    print("Critical: portage imports failed!")
    sys.exit(1)

from esearch.common import (CONFIG, NORMAL, COMPACT, VERBOSE, EBUILDS, OWN, pkg_version,
    error, outofdateerror, version)

# migrate this to the portage public api
# when/if it is merged into master
from esearch.flag import get_flags



def usage():
    print("esearch (%s) - Replacement for 'emerge search' with search-index" % version)
    print("")
    print(bold("Usage:"), "esearch [", darkgreen("options"), "] pattern")
    print(bold("Options:"))
    print(darkgreen("  --help") + ", " + darkgreen("-h"))
    print("    Print help message")
    print("")
    print(darkgreen("  --searchdesc") + ", " + darkgreen("-S"))
    print("    Search package descriptions as well")
    print("")
    print(darkgreen("  --fullname") + ", " + darkgreen("-F"))
    print("    Search packages full name (includes category)")
    print("")
    print(darkgreen("  --instonly") + ", " + darkgreen("-I"))
    print("    Find only packages which are installed")
    print("")
    print(darkgreen("  --notinst") + ", " + darkgreen("-N"))
    print("    Find only packages which are not installed")
    print("")
    print(darkgreen("  --exclude=") + "xpattern" + ", " + darkgreen("-x"), "xpattern")
    print("    Exclude packages matching xpattern from search result")
    print("")
    print(darkgreen("  --compact") + ", " + darkgreen("-c"))
    print("    More compact output format")
    print("")
    print(darkgreen("  --verbose") + ", " + darkgreen("-v"))
    print("    Give a lot of additional information (slow!)")
    print("")
    print(darkgreen("  --ebuild") + ", " + darkgreen("-e"))
    print("    View ebuilds of found packages")
    print("")
    print(darkgreen("  --own=") + "format" + ", " + darkgreen("-o"), "format")
    print("    Use your own output format, see manpage for details of format")
    print("")
    print(darkgreen("  --directory=") + "dir" + ", " + darkgreen("-d"), "dir")
    print("    Use dir as directory to load esearch index from")
    print("")
    print(darkgreen("  --nocolor") + ", " + darkgreen("-n"))
    print("    Don't use ANSI codes for colored output")

    sys.exit(0)



def mypkgcmp(pkg1, pkg2):
    return pkgcmp(pkg1[:3], pkg2[:3])


def searchEbuilds(path, portdir=True, searchdef="", repo_num="",
        config=None, data=None):
    pv = ""
    pkgs = []
    nr = len(data['ebuilds']) + 1

    if portdir:
        rep = darkgreen("Portage    ")
    else:
        rep = red("Overlay "+str(repo_num)+"  ")

    if isdir(path):
        filelist = listdir(path)

        for file in filelist:
            if file[-7:] == ".ebuild":
                pv = file[:-7]
                pkgs.append(list(pkgsplit(pv)))
                pkgs[-1].append(path + file)
                if searchdef != "" and pv == searchdef:
                    data['defebuild'] = (searchdef, pkgs[-1][3])
        if not portdir:
            config['found_in_overlay'] = True
        pkgs.sort(key=cmp_sort_key(mypkgcmp))
        for pkg in pkgs:
            rev = ""
            if pkg[2] != "r0":
                rev = "-" + pkg[2]
            data['output'].append(" " + rep + " [" + bold(str(nr)) + "] " +
                pkg[0] + "-" + pkg[1] + rev + "\n")
            data['ebuilds'].append(pkg[len(pkg)-1])
            nr += 1


def parseopts(opts, config=None):

    if config is None:
        config = CONFIG

    if len(opts[1]) == 0:
        usage()

    for a in opts[0]:
        arg = a[0]
        if arg in ("-h", "--help"):
            usage()
        if arg in ("-S", "--searchdesc"):
            config['searchdesc'] = True
        elif arg in ("-F", "--fullname"):
            config['fullname'] = True
        elif arg in ("-I", "--instonly"):
            config['instonly'] = True
        elif arg in ("-N", "--notinst"):
            config['notinst'] = True
        elif arg in ("-c", "--compact"):
            config['outputm'] = COMPACT
        elif arg in ("-v", "--verbose"):
            config['outputm'] = VERBOSE
        elif arg in ("-e", "--ebuild"):
            config['portdir'] = settings["PORTDIR"]
            config['overlay'] = settings["PORTDIR_OVERLAY"]
            config['outputm'] = EBUILDS
        elif arg in ("-x", "--exclude"):
            config['exclude'].append(a[1])
        elif arg in ("-o", "--own"):
            config['outputm'] = OWN
            config['outputf'] = a[1]
        elif arg in ("-d", "--directory"):
            config['esearchdbdir'] = a[1]
            if not exists(config['esearchdbdir']):
                error("directory '" + darkgreen(config['esearchdbdir']) +
                    "' does not exist.", stderr=config['stderr'])
        elif arg in ("-n", "--nocolor"):
            nocolor()
    if config['fullname'] and config['searchdesc']:
        error("Please use either " + darkgreen("--fullname") +
            " or " + darkgreen("--searchdesc"), stderr=config['stderr'])
    return config


def loaddb(config):
    """Loads the esearchdb"""
    try:
        sys.path.append(config['esearchdbdir'])
        from esearchdb import db
    except ImportError:
        error("Could not find esearch-index. Please run " +
            green("eupdatedb") + " as root first", stderr=config['stderr'])
    except SyntaxError:
        raise
    try:
        from esearchdb import dbversion
        if dbversion < config['needdbversion']:
            outofdateerror(config['stderr'])
    except ImportError:
        outofdateerror(config['stderr'])
    return db


def do_compact(pkg):
    prefix0 = " "
    prefix1 = " "

    if pkg[3] == pkg[4]:
        color = darkgreen
        prefix1 = "I"
    elif not pkg[4]:
        color = darkgreen
        prefix1 = "N"
    else:
        color = turquoise
        prefix1 = "U"

    if pkg[2]:
        prefix0 = "M"

    return " [%s%s] %s (%s):  %s" % \
            (red(prefix0), color(prefix1), bold(pkg[1]), color(pkg[3]), pkg[7])


def do_normal(pkg, verbose):
    data = []
    if not pkg[4]:
        installed = "[ Not Installed ]"
    else:
        installed = pkg[4]

    if pkg[2]:
        masked = red(" [ Masked ]")
    else:
        masked = ""

    data.append("%s  %s%s\n      %s %s\n      %s %s" % \
            (green("*"), bold(pkg[1]), masked,
            darkgreen("Latest version available:"), pkg[3],
            darkgreen("Latest version installed:"), installed))

    if verbose:
        mpv = best(portdb.xmatch("match-all", pkg[1]))
        iuse_split, final_use = get_flags(mpv, final_setting=True)
        iuse = ""
        use_list = []
        for ebuild_iuse in iuse_split:
            use = ebuild_iuse.lstrip('+-')
            if use in final_use:
                use_list.append(red("+" + use) + " ")
            else:
                use_list.append(blue("-" + use) + " ")
        use_list.sort()
        iuse = ' '.join(use_list)
        if iuse == "":
            iuse = "-"

        data.append("      %s         %s\n      %s       %s" % \
                (darkgreen("Unstable version:"), pkg_version(mpv),
                 darkgreen("Use Flags (stable):"), iuse))

    data.append("      %s %s\n      %s    %s\n      %s %s\n      %s     %s\n" % \
            (darkgreen("Size of downloaded files:"), pkg[5],
             darkgreen("Homepage:"), pkg[6],
             darkgreen("Description:"), pkg[7],
             darkgreen("License:"), pkg[8]))
    return data, False


def do_own(pkg, own):
    # %c => category
    # %n => package name
    # %p => same as %c/%n
    # %m => masked
    # %va => latest version available
    # %vi => latest version installed
    # %s => size of downloaded files
    # %h => homepage
    # %d => description
    # %l => license


    own = own.replace("%c", pkg[1].split("/")[0])
    own = own.replace("%n", pkg[0])
    own = own.replace("%p", pkg[1])

    masked = ""
    if pkg[2]:
        masked = "masked"
    own = own.replace("%m", masked)
    own = own.replace("%va", pkg[3])

    installed = pkg[4]
    if not installed:
        installed = ""
    own = own.replace("%vi", installed)
    own = own.replace("%s", pkg[5])
    own = own.replace("%h", pkg[6])
    own = own.replace("%d", pkg[7])
    own = own.replace("%l", pkg[8])

    own = own.replace("\\n", "\n")
    own = own.replace("\\t", "\t")
    return own


def create_regex(config, pattern):
    """Creates a regular expression from a pattern string"""
    # Hacks for people who aren't regular expression gurus
    if pattern == "*":
        pattern = ".*"
    else:
        pattern = re.sub("\+\+", "\+\+", pattern)

    try:
        regex = re.compile(pattern, re.IGNORECASE)
    except re.error:
        error("Invalid regular expression.", stderr=config['stderr'])

    fullname = (config['fullname'] or '/' in pattern) and not config['searchdesc']

    return pattern, regex, fullname


def create_regexlist(config, patterns):
    """Creates a list of regular expressions and other data
    for use in db searches for each pattern in the list of patterns"""
    regexlist = []
    for pattern in patterns:
        pattern, regex, fullname = create_regex(config, pattern)
        regexlist.append([regex, pattern, "", 0, fullname])
    return regexlist


def searchdb(config, patterns, db=None):
    """Gutted out old search method.
    Now just calls the broken up functions.
    For api compatibility.
    """
    regexlist = create_regexlist(config, patterns)
    found = search_list(config, regexlist, db)
    if config['exclude']:
        found = filter_excluded(config, found)
    return output_results(config, regexlist, found)


# turns out this is slower :(
def search1(config, regexlist, db=None):
    """Test search method that performs
    multiple reg expr. checks for each pkg
    """
    data = {}

    #for regex, pattern, foo, foo, fullname in regexlist:
    for p in range(len(regexlist)):
        data[regexlist[p][1]] = []

    for pkg in db:
        for regex, pattern, foo, foo, fullname in regexlist:
            found = False

            if config['instonly'] and not pkg[4]:
                continue
            elif config['notinst'] and pkg[4]:
                continue

            if  fullname and regex.search(pkg[1]):
                found = True
            elif regex.search(pkg[0]):
                found = True
            elif config['searchdesc'] and regex.search(pkg[7]):
                found = True

            if found:
                data[pattern].append(pkg)
    return data


def search_list(config, regexlist, db=None):
    """An optimized regular expression list db search"""
    data = {}

    for regex, pattern, foo, foo, fullname in regexlist:
        data[pattern] = search(config, regex, fullname, db)
    return data


def search(config, regex, fullname, db):
    """An optimized single regular expression db search"""
    data = []

    for pkg in db:
        found = False

        if config['instonly'] and not pkg[4]:
            continue
        elif config['notinst'] and pkg[4]:
            continue

        if fullname:
            found = regex.search(pkg[1])
        elif config['searchdesc']:
            found = regex.search(pkg[7])
        else:
            found = regex.search(pkg[0])

        if found:
            data.append(pkg)
    return data


def is_excluded(config, regex, fullname, pkg):
    """Checks if pkg matches the given exclude regex"""

    if fullname:
        return regex.search(pkg[1])
    elif config['searchdesc']:
        return regex.search(pkg[7])
    else:
        return regex.search(pkg[0])


def filter_excluded(config, found):
    """Filters the list of found packages with the --exclude pattern"""

    for pattern in config['exclude']:
        foo, regex, fullname = create_regex(config, pattern)

        for key in found.keys():
            found[key] = list(filter((lambda pkg: not is_excluded(config, regex, fullname, pkg)), found[key]))

    return found


def output_results(config, regexlist, found):
    data = {}
    data['ebuilds'] = []
    data['defebuild'] = (0, 0)
    i = 0
    for regex, pattern, foo, foo, fullname in regexlist:
        count = 0
        data['output'] = []
        for pkg in found[pattern]:
            if config['outputm'] in (NORMAL, VERBOSE):
                newdata, _continue = do_normal(pkg,
                    config['outputm'] == VERBOSE)
                data['output'] += newdata
                if _continue:
                    continue
            elif config['outputm'] in (COMPACT, EBUILDS):
                data['output'].append(do_compact(pkg))

            elif config['outputm'] == OWN:
                data['output'].append(do_own(pkg, config['outputf']))

            if config['outputm'] == EBUILDS:
                if count == 0:
                    searchdef = pkg[0] + "-" + pkg[3]
                else:
                    searchdef = ""

                searchEbuilds("%s/%s/" % (config['portdir'], pkg[1]),
                    True, searchdef, "", config, data)
                if config['overlay']:
                    repo_num=1
                    for repo in config['overlay'].split():
                        searchEbuilds("%s/%s/" % ( repo, pkg[1]),
                            False, searchdef,repo_num, config, data)
                        repo_num += 1

            count += 1

        regexlist[i][2] = "\n".join(data['output'])
        regexlist[i][3] = count
        i += 1

    for regex, pattern, output, count, foo in regexlist:
        if config['outputm'] in (NORMAL, VERBOSE):
            print("[ Results for search key :", bold(pattern), "]")
            print("[ Applications found :", bold(str(count)), "]\n")
            try:
                print(output, end=' ')
                print("")
            except IOError:
                pass
        else:
            print(output)



    if config['outputm'] == EBUILDS:
        if config['overlay'] and config['found_in_overlay']:
            repo_num=1
            for repo in config['overlay'].split():
                print(red("Overlay "+str(repo_num)+" : "+repo))
                repo_num += 1

        if count != 0:
            if count > 1:
                data['defebuild'] = (0, 0)

            if len(data['ebuilds']) == 1:
                nr = 1
            else:
                if data['defebuild'][0] != 0:
                    print(bold("\nShow Ebuild"), " (" + darkgreen(data['defebuild'][0]) + "): ", end=' ')
                else:
                    print(bold("\nShow Ebuild: "), end=' ')
                try:
                    nr = sys.stdin.readline()
                except KeyboardInterrupt:
                    return False
            try:
                editor = getenv("EDITOR")
                if editor:
                    system(editor + " " + data['ebuilds'][int(nr) - 1])
                else:
                    print("")
                    error("Please set EDITOR", False, stderr=config['stderr'])
            except IndexError:
                print("", file=config['stderr'])
                error("No such ebuild", False, stderr=config['stderr'])
            except ValueError:
                if data['defebuild'][0] != 0:
                    system(editor + " " + data['defebuild'][1])
                else:
                    print("", file=config['stderr'])
                    error("Please enter a valid number", False,
                        stderr=config['stderr'])
    return True


def main():
    try:
        opts = getopt(sys.argv[1:], "hSFINcveo:d:x:n",
            ["help", "searchdesc", "fullname", "instonly", "notinst", "compact",
             "verbose", "ebuild", "own=", "directory=", "exclude=", "nocolor"
            ])
    except GetoptError as errmsg:
        error(str(errmsg) + "(see " + darkgreen("--help") +
            " for all options)" + '\n')
    config = parseopts(opts)
    db = loaddb(config)
    regexlist = create_regexlist(config, opts[1])
    found = search_list(config, regexlist, db)
    if config['exclude']:
        found = filter_excluded(config, found)
    success = output_results(config, regexlist, found)

    # sys.exit() values are opposite T/F
    sys.exit(not success)

if __name__ == '__main__':

    main()
