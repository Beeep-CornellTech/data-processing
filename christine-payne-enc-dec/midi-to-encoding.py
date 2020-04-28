import argparse
import os
import numpy as np
from math import floor
from pathlib import Path
import json
import pretty_midi

############## to be set before running the encoding operation
#piano, violin, acoustic bass, fretless bass, guitar
#0, 40, 32, 35, 24
#############

## jazz
#instr_programs_to_keep = [0, 40, 32, 35, 24]

### Jazz mapping
# instr_prefix_mapping = {
#     0: 'p',
#     40: 'v',
#     32: 'a',
#     35: 'f',
#     24: 'g'
# }

## metal
instr_programs_to_keep = [19, 4, 30, -1, 29, 34, 27, 25]

## metal
instr_prefix_mapping = {
    -1: 'p', ## drums (percussion)
    19: 'c', ## church organ
    4: 'e',  ## electric piano
    30: 'd', ## distortion guitar
    29: 'o', ## overdriven guitar
    34: 'b', ## electric bass
    27: 'g', ## electric guitars
    25: 'a'  ## acoustic guitar steel
}

instr_programs_mapping = {
    19: [50,42,41,109,20,53,9,80,85,81,87,31,120,35, 48, 49],
    4:  [5],
    30: [],
    -1:  [117, 112, 93, 91,95, 94, 118],
    29: [],
    34: [33, 36, 32],
    27: [68, 45, 110, 69, 71, 86, 82, 26],
    25: [40, 41, 22, 24, 106]
} # FILL if instruments are mapped

include_percussion = True


instr_mapping = None

def get_mapping_for_instr(program):
    global instr_mapping
    if instr_mapping is None:
        instr_mapping = {}
        for good_instr in instr_programs_mapping:
            instr_to_convert = instr_programs_mapping[good_instr]
            for i in instr_to_convert:
                instr_mapping[i] = good_instr


    if program in instr_mapping:
        return instr_mapping[program]
    else:
        return -1

def stream_to_chordwise(s, note_range, note_offset, sample_freq): 

    numInstruments=len(instr_programs_to_keep) ## selected instruments for each music style

    maxTimeStep = floor(s.get_end_time() * sample_freq)+1  ## this is the maximum length of music * sample_freq
    score_arr = np.zeros((maxTimeStep, numInstruments, note_range))

    notes=[]
    
    ## for every note, record its midi value, when it is played, how long it is played and it's instrument ID
    ## for when and how long, the values are multiplied by sample_freq. This makes the music slower as 
    ## smaller notes are now sample_freq times longer
    for instr in s.instruments:
        instrumentID = instr.program
        if instr.is_drum == True:
            if include_percussion == False:
                continue ## skip if include_percussion is False
            else:
                if instrumentID == 0:
                    instrumentID = -1 ## hardcoded for drums here

        if not instrumentID in instr_programs_to_keep:
            mapped_id = get_mapping_for_instr(instrumentID)
            if mapped_id == -1:
                continue # skip instrument
            else:
                instrumentID = mapped_id

        for n in instr.notes:
            notes.append((n.pitch-note_offset, floor(n.start*sample_freq), floor((n.end - n.start)*sample_freq), instrumentID))
   
    for n in notes:
        pitch=n[0]
        while pitch<0:
            pitch+=12 ## increase by an octave
        while pitch>=note_range:
            pitch-=12 ## decrease by an octave

        ### for now, ignoring the instrument musical range

        # if n[3]==instr_mapping['ids']['Violin']:      #Violin lowest note is v22
        #     while pitch<22:
        #         pitch+=12
        # if n[3]==instr_mapping['ids']['Acoustic Guitar']:      #Guitar lowest note is v7
        #     while pitch<7:
        #         pitch+=12

        ## offset, instrument, note
        score_arr[n[1], instr_programs_to_keep.index(n[3]), pitch]=1                  # Strike note
        score_arr[n[1]+1:n[1]+n[2], instr_programs_to_keep.index(n[3]), pitch]=2      # Continue holding note
            
    score_string_arr=[]

    for timestep in score_arr:
        for i in reversed(instr_programs_to_keep):
            prefix = instr_prefix_mapping[i]
            instr_idx = instr_programs_to_keep.index(i)
            score_string_arr.append(prefix+''.join([str(int(note)) for note in timestep[instr_idx]]))      

    return score_string_arr
    
def add_modulations(score_string_arr):

    modulated=[]
    note_range=len(score_string_arr[0])-1
    for i in range(0,12):
        for chord in score_string_arr:
            padded='000000'+chord[1:]+'000000'
            modulated.append(chord[0]+padded[i:i+note_range])

    return modulated

def chord_to_notewise(long_string, sample_freq):

    translated_list=[]
    for j in range(len(long_string)):
        chord=long_string[j]
        next_chord=""
        for k in range(j+1, len(long_string)):
            if long_string[k][0]==chord[0]: ## get the next chord of the same instrument
                next_chord=long_string[k]
                break
        prefix=chord[0]
        chord=chord[1:]
        next_chord=next_chord[1:]
        for i in range(len(chord)):
            if chord[i]=="0":
                continue
            note=prefix+str(i)                
            if chord[i]=="1":
                translated_list.append(note)
            # If chord[i]=="2" do nothing - we're continuing to hold the note
            # unless next_chord[i] is back to "0" and it's time to end the note.
            if next_chord=="" or next_chord[i]=="0":      
                translated_list.append("end"+note)
                      
        if prefix=="p": ## why????
            translated_list.append("wait")
    
    i=0
    translated_string=""
    while i<len(translated_list):
        wait_count=1
        if translated_list[i]=='wait':
            while wait_count<=sample_freq*2 and i+wait_count<len(translated_list) and translated_list[i+wait_count]=='wait':
                wait_count+=1
            translated_list[i]='wait'+str(wait_count)
        translated_string+=translated_list[i]+" "
        i+=wait_count
    
    return translated_string

def translate_folder_path(output_folder, note_range, sample_freq, style):
    START_PATH = Path(output_folder)
    note_range_folder="note_range"+str(note_range)
    sample_freq_folder="sample_freq"+str(sample_freq)
    directory=START_PATH/style
    directory=directory/note_range_folder/sample_freq_folder
    directory.mkdir(parents=True, exist_ok=True)
    return directory
    
#midi_file, output_folder, sample_freqs, note_ranges, note_offsets, replace)
def translate_piece(midi_dir, fname, output_folder, sample_freqs, note_ranges, note_offsets, replace, music_style):
    # Check if file has already been done previously:
    if not replace:
        exists=True
        for sample_freq in sample_freqs:
            for note_range in note_ranges:    
                seek_file=fname[:-4]+".txt"
                notewise_directory=translate_folder_path(output_folder, note_range, sample_freq, music_style)
                exists = exists and os.path.isfile(notewise_directory/seek_file)
                if not exists:
                    break
            if not exists:
                break
        if exists:
            print("Skipping file: Output files already exist. Use --replace to override this and retranslate everything.")
            return
                
    try:
        fpath = os.path.join(midi_dir, fname)
        midi_data = pretty_midi.PrettyMIDI(fpath)
    except:
        print("Skipping file: {}".format(fname))
        return


    for sample_freq in sample_freqs:
        for note_range in note_ranges:
        
            ## convert midi -> "['p000000101010000', .....]" format
            score_string_arr = stream_to_chordwise(midi_data, note_range, note_offsets[note_range], sample_freq)
            if len(score_string_arr)==0:
                print("Skipping file: Unknown instrument")
                return
       
            score_string_arr=add_modulations(score_string_arr)
    
            # Translate to notewise format
            score_string=chord_to_notewise(score_string_arr, sample_freq)

            # Write notewise format to file
            notewise_directory=translate_folder_path(output_folder, note_range, sample_freq, music_style)
            #os.chdir(notewise_directory)
            out_fpath = os.path.join(notewise_directory, fname[:-4]+".txt")
            f=open(out_fpath,"w+")
            f.write(score_string)
            f.close()
    print("Success")
    
def main(midi_dir, replace, output_folder, style):
          
    sample_freqs=[4,12]
    note_ranges=[38,62]
    note_offsets={}
    note_offsets[38]=45
    note_offsets[62]=33

    (_, _, files) = next(os.walk(midi_dir)) # python3 syntax
    midi_files = [f for f in files if '.mid' in f]

    f_idx = 0
    for midi_file in midi_files:
        print("Processing file: {}/{}".format((f_idx + 1), len(midi_files)))
        translate_piece(midi_dir, midi_file, output_folder, sample_freqs, note_ranges, note_offsets, replace, style)

if __name__ == "__main__":
    parser = argparse.ArgumentParser() 
    parser.add_argument('--midi_dir', dest="midi_dir", help="Specify directory path of midi files to encode")
    parser.add_argument('--output', dest="output", help="Specify directory path to store encoded files")                     
    parser.add_argument('--style', dest="style", help="Specify style of music (jazz/metal etc.)")                     
    parser.set_defaults(style="jazz")
    parser.add_argument('--replace', dest="replace", action="store_true", help="Retranslate and replace existing files (defaults to skip)")
    
    parser.set_defaults(replace=False)

    args = parser.parse_args()

    if not os.path.isdir(args.midi_dir):
        print("Midi dir given is not a directory")
        os.exit(1)
    if not os.path.isdir(args.output):
        print("Output dir given is not a directory")
        os.exit(1)
    

    main(args.midi_dir, args.replace, args.output, args.style)