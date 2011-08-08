''' SIMPER = Solium Infernum MultiPlayer helpER

Copyright (C) 2011  PURPORC

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
    
Created on 28/04/2011

@author: PURPORC
'''

import argparse
import threading
import Queue
import time
import os
import filecmp
import re
import shutil
import datetime
from collections import namedtuple


class SoliumInfernumMultiplayerHelper(object):

    patstr = "[Tt]urn\s*(\d+)$"
    pat = re.compile(patstr)
 

    def __init__(self, setup_dict):
        # initialize blank
        self.turn_dictionary = {}
        self.latest_dirstr = ''
        self.latest_save_turn_local = ''
        
        # specifics of the game of interest
        if 'game_name' in setup_dict:
            self.dropbox = setup_dict.dropbox
            self.si_multiplayersaves = setup_dict.si_multiplayersaves
            self.game_name = setup_dict.game_name
            self.game_save_filename = setup_dict.game_save_filename
            self.archive_subdirectory = setup_dict.archive_subdirectory
            self.player_turn_filename = setup_dict.player_turn_filename
        else:
            self.dropbox = "C:\\Users\\PURPORC\\dropbox\\Dropbox"
            self.si_multiplayersaves = "C:\\Users\\PURPORC\\Documents\\SoliumInfernumGame\\MultiPlayerSaves"
            self.game_name = "Downsizest"
            self.game_save_filename = "DownsizestMain.sav"  # can we build that from the game name?
            self.archive_subdirectory = 'Archive'
            self.player_turn_filename = "PURPORC.trn"
                
        
    @property   
    def archive_directory(self):
        return self.archive_subdirectory

    @property
    def game_local(self):
        return self.si_multiplayersaves + os.sep + self.game_name.replace(" ", "") + os.sep
    
    @property
    def game_dropbox(self):
        return self.dropbox + os.sep + self.game_name + os.sep
      
    def load_known_turn(self):
        ''' Read the saved file which reflects the current turn loaded.
        '''
        tf = ".known_turn.txt"
        if tf in os.listdir(self.game_local):
            turn_info_file = open(self.game_local + tf, "r")
            
            if turn_info_file:
                self.latest_save_turn_local = turn_info_file.read()

    def save_known_turn(self):
        ''' Record the current turn of the loaded save file.
        '''
        if not self.latest_save_turn_local == self.latest_dirstr: # avoid rewriting to preserve mtime
            turn_info_file = open(self.game_local + ".known_turn.txt", "w")
            turn_info_file.write(self.latest_dirstr) 
    


    def common(self):
        ''' Prime object with the basics.
        '''
        for d in os.listdir(self.game_dropbox) :
            match = re.match(SoliumInfernumMultiplayerHelper.pat, d)
            if match:
                self.turn_dictionary[int(match.group(1))] = match.group(0) 
        # print self.turn_dictionary
        if self.turn_dictionary:
            self.latest_dirstr = self.turn_dictionary[max(self.turn_dictionary.keys())]
        else:
            self.latest_dirstr = None
        self.load_known_turn()
        
    def get_stats(self):
        ''' Assemble some statistics about the progress of the game.
        '''
        
        TurnRecord = namedtuple('TurnRecord', 'turn_dir, last_player, last_player_delay, turn_start, turn_end, turn_ready_for_host, turn_duration_nonhost, turn_duration_host, turn_duration, player_infos')
        PlayerInfo = namedtuple('PlayerInfo', 'player_turn_file, player_turn_end, player_turn_duration')
        turns = {}
        dir_list = []
        # dir_list = os.listdir(self.game_dropbox + os.sep + "Archive")
        # dir_list.extend(os.listdir(self.game_dropbox))
        for (dirpath, dirnames, filenames) in os.walk(self.game_dropbox):
            for tcd in dirnames:
                match = re.match(SoliumInfernumMultiplayerHelper.pat, tcd)
                if match:
                    turn_number = int(match.group(1))
                    dir_list.append((turn_number, os.path.join(dirpath, tcd)))
                else:
                    # not a turn directory for whatever reason
                    continue
        
        for turn_number, dirpath in dir_list:
            if not self.game_save_filename in os.listdir(dirpath):
                # directory lacks the save file.
                continue 
            turn_available = datetime.datetime.fromtimestamp(os.path.getmtime(os.path.join(dirpath , self.game_save_filename)))
            turn_processed = datetime.datetime.fromtimestamp(os.path.getctime(dirpath))
            
            players_info = []
            last_player = ''
            last_player_delay = datetime.timedelta(0)
            max_turn_taken = turn_available
            
            for filenames in os.listdir(dirpath) :
                if filenames == self.game_save_filename or not filenames.endswith(".trn"):
                    continue
                turn_taken = datetime.datetime.fromtimestamp(os.path.getmtime(os.path.join(dirpath, filenames)))
                if turn_taken >= max_turn_taken or last_player == '':
                    if turn_taken == max_turn_taken :
                        last_player += filenames
                    else:
                        last_player_delay = turn_taken - max_turn_taken
                        last_player = filenames  
                    max_turn_taken = turn_taken
                else:
                    last_player_delay = min(last_player_delay, max_turn_taken - turn_taken)
                        
                pi = PlayerInfo(player_turn_file=filenames
                                , player_turn_end=turn_taken
                                , player_turn_duration=turn_taken - turn_available)
                players_info.append(pi)
                
            turn_info = TurnRecord(turn_dir=dirpath
                                  , last_player=last_player
                                  , last_player_delay=last_player_delay
                                  , turn_start=turn_available
                                  , turn_end=turn_processed
                                  , turn_ready_for_host=max_turn_taken
                                  , turn_duration_nonhost=max_turn_taken - turn_available
                                  , turn_duration_host=max(datetime.timedelta(0), turn_processed - max_turn_taken)
                                  , turn_duration=turn_processed - turn_available
                                  , player_infos=players_info)
            turns[turn_number] = turn_info
        
        return turns
    
    def update(self, interesting_turn=None):
        '''
        Retrieve a turn from the dropbox
        
        either the current latest turn or a previous turn
        '''
        self.common()
        
        if interesting_turn:
            self.latest_dirstr = self.archive_directory + os.sep + 'Turn ' + str(interesting_turn)
            if 'Turn ' + str(interesting_turn) not in os.listdir(self.game_dropbox + self.archive_directory):
                print "Can't find turn %s directory: '%s'" % (interesting_turn, self.game_dropbox + self.latest_dirstr)
                return
                
        
        if self.game_save_filename in os.listdir(self.game_dropbox + self.latest_dirstr):
            print 'found save for turn', max(self.turn_dictionary.keys())
            if not interesting_turn is None or not self.player_turn_filename in os.listdir(self.game_dropbox + self.latest_dirstr) or raw_input('found my turn file already there...  r u sure? [y]/[N] : ') == 'y':
                if self.get_save_name(self.latest_dirstr) in os.listdir(self.game_local):
                    # retrieve the saved save with my turn choices embedded
                    shutil.copy(self.game_local + os.sep + self.get_save_name(self.latest_dirstr), self.game_local + os.sep + self.game_save_filename)
                    self.save_known_turn()
                elif self.game_save_filename in os.listdir(self.game_local) and filecmp._do_cmp(self.game_local + self.game_save_filename, self.game_dropbox + self.latest_dirstr + os.sep + self.game_save_filename) :  # filecmp._do_cmp because I only care about the contents, no metadata shortcuts.
                    print "got it already"
                else:
                    shutil.copy(self.game_dropbox + self.latest_dirstr + os.sep + self.game_save_filename, self.game_local)
                    if self.player_turn_filename in os.listdir(self.game_dropbox + self.latest_dirstr):
                        shutil.copy(self.game_dropbox + self.latest_dirstr + os.sep + self.player_turn_filename, self.game_local)
                    self.save_known_turn()
                    print "copied"
        

    def get_save_name(self, turn_dir_name):
        return self.game_save_filename + "." + turn_dir_name.replace(self.archive_subdirectory + os.sep, "").replace("Turn ", "")

    def commit(self):
        '''
        Commit current saved turn to the dropbox
         
        check that found latest turn is the same as my current turn
        (by file comparison)
        otherwise we could do save/load out of sequence and upload turn X to turn Y folder. 
        '''
        self.common()
        if self.latest_save_turn_local != self.latest_dirstr:
            print 'Turn file applies to a different game save turn directory: \n  my turn:     ' + self.latest_save_turn_local + "\n  server turn: " + self.latest_dirstr + "\n\nNo action."
        elif os.path.getmtime(self.game_local + self.player_turn_filename) < os.path.getmtime(self.game_local + ".known_turn.txt") and not raw_input('Turn file is older than the time we copied the save file, r u sure? [y]/[N] : ') == 'y' : 
            # want to check dates on the two files
            print 'Turn file is older than the dropbox game save file'
        elif not self.player_turn_filename in os.listdir(self.game_dropbox + self.latest_dirstr) or raw_input('found my turn file already there...  r u sure? [y]/[N] : ') == 'y':
            shutil.copy(self.game_local + self.player_turn_filename, self.game_dropbox + self.latest_dirstr + os.sep + self.player_turn_filename) 
            shutil.copy(self.game_local + self.game_save_filename, self.game_local + os.sep + self.get_save_name(self.latest_dirstr)) # copy to local location with turn no. extension
            print 'Copied new turn up to the shared folder.'


def do_reprompt():
    ''' Print the main prompt.
    '''
    print "\nAction [U]pdate, [c]ommit, [r]eplay, [s]tats, or [q]uit: " ,

def check_thread(q, properties):
    ''' The thread which keeps an eye on the dropbox for new submissions and turns.
    '''
    notified = False
    reprompt = False
    last_known_player_turn = None
    i = 30
    while 1:
        i += 1
        if not q.empty():
            msg = q.get()
            if msg == 'stop':
                break
        
        if i < 20:
            time.sleep(1)
            continue
        else:
            i = 0
                
        sih = SoliumInfernumMultiplayerHelper(properties)
        sih.common()
            
        if sih.latest_dirstr != sih.latest_save_turn_local:
            if not notified:
                print  "\n\n" + datetime.datetime.now().strftime("%H:%M %d/%m") + " !! there is a new turn !!"
                notified = True
                reprompt = True
        else:
            notified = False
            try:
                lots_of_info = sih.get_stats()
                current_turn = lots_of_info[max(sih.turn_dictionary.keys())]
                
                if current_turn.player_infos:
                    last_player_info = sorted(current_turn.player_infos, key=lambda x: x.player_turn_end)[-1]
                    last_player_time = format_timedelta(last_player_info.player_turn_duration)
                if  last_known_player_turn != current_turn.last_player:
                    print "\n\n%s New turn from %s. %s after turn available and %s after the previous player.\n" % (datetime.datetime.now().strftime("%H:%M %d/%m") , current_turn.last_player.replace(".trn", "") , last_player_time, format_timedelta(current_turn.last_player_delay))
                    last_known_player_turn = current_turn.last_player
                    reprompt = True
            except Exception, e:
                print e
            
        if reprompt:
            do_reprompt()
            reprompt = False
                      
        del sih
    

def main_loop(properties):
    ''' The user-interactive prompt and response
    '''
    keepGoing = 1
    while keepGoing:
        while 1:
            do_reprompt()
            action = raw_input() 
            if len(action) > 0:
                action = action[0]
                if action != "S":
                    action = action.lower()
            if action == 'q':
                keepGoing = False
                break
            if action == 'c' or action == 'u' or action == 'r' or action == '' or action == 's' or action == 'S':
                break
            print 'Unknown command...'
        do_work(action, properties)
        
        
def format_rpad(string_to_format, width, padding_char=" ", wrap_open="", wrap_close=""):
    ''' Wrap string in specified strings and pad to fixed width.  
    '''
    out = wrap_open + string_to_format + wrap_close
    if len(padding_char) == 1:
        out = out.ljust(width, padding_char)
    return out

def format_timedelta(td):
    ''' Make timedeltas look sensible for output.
    '''
    if td == 0:
        return ""
    sec = td.total_seconds()
    h, rem = divmod(sec, 60 ** 2)
    m, s = divmod(rem, 60)
    return "%d:%02d:%02d" % (h, m, s)

def format_row(row, lens, sep, pad, wrap_open, wrap_close):
    ''' Generate a string from the row data and formatting settings.
    '''
    frp = lambda s, width: format_rpad(s, width, pad, wrap_open, wrap_close)
    new_sep = pad + sep + pad
    middle = new_sep.join(frp(x, y) for x, y in zip(row, lens))
         
    return sep + pad + middle + pad + sep

def format_table(data, heads, sep="|", pad=" ", padhead="=", wrap_open="", wrap_close=""):
    ''' Generate a string from the headers and data using formatting.
    ''' 
    lens = [ max(len(x) for x in z) for z in zip(*([heads] + data)) ]
    if len(padhead) == 1:
        lines = list(format_rpad("", x, padhead) for x in lens) 
    else:
        lines = ["", "", "", "", "", "", "", "", ""]
    frd = lambda row: format_row(row, lens, sep, pad, wrap_open, wrap_close) 
    out = "\n".join([ format_row(heads, lens, sep, pad, wrap_open, wrap_close)
                     , format_row(lines, lens, sep, padhead, wrap_open, wrap_close)
                     ] + list(frd(row) for row in data)
                     + 
                     [ format_row(lines, lens, sep, padhead, wrap_open, wrap_close)
                      , format_row(heads, lens, sep, pad, wrap_open, wrap_close)
                     ])
    return out
        
def do_work(action, properties):
    ''' Process an action.
    '''
    
    try:    
        sih = SoliumInfernumMultiplayerHelper(properties)
        
        if action == 'u' or action == '':
            sih.update()
        elif action == 'c':
            sih.commit()
        elif action == 'r':
            interesting_turn = 1
            ri = raw_input("Which turn do you want to load up? ")
            try:
                interesting_turn = int(ri)
            except Exception, e:
                print "Sorry, I didn't understand '%s' as a turn number." % ri
                return
            sih.update(interesting_turn)
        elif action == 's' or action == 'S':
            stats = sih.get_stats()
            heads = ("Turn", "Count", "Last Player", "Last player delay", "Turn Start", "Turn End", "Turn Duration", "Host Duration", "Player turn submission order")
            output = []
            for tn, tr in stats.items():
                output.append((str(tn), str(len(tr.player_infos)), tr.last_player.replace(".trn", ""), format_timedelta(tr.last_player_delay)
                                 , tr.turn_start.strftime("%A %d/%m"), tr.turn_end.strftime("%A %d/%m")
                                 , format_timedelta(tr.turn_duration_nonhost), format_timedelta(tr.turn_duration_host)
                                 , "-".join(pi.player_turn_file.replace(".trn", "")  for pi in sorted(tr.player_infos, key=lambda info: info.player_turn_end)) 
                                 ))
            if action == 's':
                print "\n" , format_table(output, heads)
            else:        
                print format_table(output, heads, ",", "", "", "\"", "\"")
    finally:        
        del sih

if __name__ == '__main__':
    communication_q = Queue.Queue()
    
    parser = argparse.ArgumentParser(description='SIMPER = Solium Infernum MultiPlayer helpER.')
    parser.add_argument('dropbox',
                        help='the location of your dropbox folder.\ne.g. "C:\\Users\\PURPORC\\dropbox\\Dropbox"')
    parser.add_argument('si_multiplayersaves',
                        help='the location of your dropbox folder.\ne.g. "C:\\Users\\PURPORC\\Documents\\SoliumInfernumGame\\MultiPlayerSaves"')
    parser.add_argument('game_name',
                       help='the name of the game without spaces.\ne.g. "Downsizider"')
    parser.add_argument('game_save_filename',
                       help='Game Turn filename. e.g. "DownsiziderMain.sav"')
    parser.add_argument('archive_subdirectory',
                       help='where old turns go to die\ne.g. "Archive" or "Old Turns"')
    parser.add_argument('player_turn_filename',
                       help='my save file name.\ne.g. "Purporc.trn"')
    
    game_properties = parser.parse_args()
    
    t = threading.Thread(target=check_thread, args=(communication_q, game_properties))
    t.start()
    
    
    try:
        main_loop(game_properties)
    except KeyboardInterrupt, ke:
        pass
    except Exception, ex:
        print ex.message
    finally:
        communication_q.put("stop")
    
