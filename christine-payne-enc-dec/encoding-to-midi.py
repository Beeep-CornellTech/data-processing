from pathlib import Path
import pretty_midi
import json
import argparse
import os


## jazz
# instr_programs_to_keep = [0, 40, 32, 35, 24]
# instr_prefix_mapping = {
# 	'p' : 0,
# 	'v' : 40,
# 	'a': 32,
# 	'f': 35,
# 	'g' : 24
# }

## metal
instr_programs_to_keep = [19, 4, 30, -1, 29, 34, 27, 25]

## metal
instr_prefix_mapping = {
	'p': -1, ## drums (percussion)
	'c': 19, ## church organ
	'e': 4,  ## electric piano
	'd': 30, ## distortion guitar
	'o': 29, ## overdriven guitar
	'b': 34, ## electric bass
	'g': 27, ## electric guitars
	'a': 25  ## acoustic guitar steel
}

num_instruments = len(instr_programs_to_keep)

def arrToStreamNotewise(score, sample_freq, note_offset):
	speed=1./sample_freq

	instrument_notes = [list() for i in range(num_instruments)]

	time_offset=0
			
	for i in range(len(score)):
		if score[i] in ["", " ", "<eos>", "<unk>"]:
			continue
		elif score[i][:3]=="end":
			if score[i][-3:]=="eoc":
				time_offset+=1
			continue
		elif score[i][:4]=="wait":
			time_offset+=int(score[i][4:])
			continue
		else:
			# Look ahead to see if an end<noteid> was generated
			# soon after.  
			duration=1
			has_end=False
			note_string_len = len(score[i])
			for j in range(1,200):
				if i+j==len(score):
					break
				if score[i+j][:4]=="wait":
					duration+=int(score[i+j][4:])
				if score[i+j][:3+note_string_len]=="end"+score[i] or score[i+j][:note_string_len]==score[i]:
					has_end=True
					break
				if score[i+j][-3:]=="eoc":
					duration+=1

			if not has_end:
				duration=12

			add_wait = 0
			if score[i][-3:]=="eoc":
				score[i]=score[i][:-3]
				add_wait = 1

			try: 

				pitch = int(score[i][1:])+note_offset
				start = time_offset*speed
				end = start + duration*speed
				note = pretty_midi.Note(velocity=100, pitch=pitch, start=start, end=end)

				instr_program = instr_prefix_mapping[score[i][0]]
				instr_idx = instr_programs_to_keep.index(instr_program)
				instrument_notes[instr_idx].append(note)
			  
			except Exception as e: 
				print(e)
				print("Unknown note: " + score[i])

			time_offset+=add_wait

	decoded_midi = pretty_midi.PrettyMIDI()
	for instr_program in instr_programs_to_keep:
		pm_instr = pretty_midi.Instrument(program=instr_program)
		if instr_program == -1:
			pm_instr = pretty_midi.Instrument(program=0, is_drum=True)	
		
		instr_idx = instr_programs_to_keep.index(instr_program)
		for n in instrument_notes[instr_idx]:
			pm_instr.notes.append(n)

		decoded_midi.instruments.append(pm_instr)

	return decoded_midi


def string_inds_to_stream(string, sample_freq, note_offset):
	score_i = string.split(" ")
	return arrToStreamNotewise(score_i, sample_freq, note_offset)

def write_mid_mp3_wav(stream, fname, sample_freq, note_offset, out):
	stream_out=string_inds_to_stream(stream, sample_freq, note_offset)
	stream_out.write(os.path.join(out, fname))

if __name__ == '__main__':
	parser = argparse.ArgumentParser() 
	parser.add_argument('--enc_dir', dest="enc_dir", help="Specify directory path of encoded files to decode")
	parser.add_argument('--output', dest="output", help="Specify directory path to store decoded midi files")                     
	parser.add_argument("--sample_freq", dest="sample_freq", help="Split beat into 4 or 12 parts", type=int)
	parser.add_argument("--note_range", dest="note_range", help="Set 38/62 note range", type=int)
	parser.add_argument("--style", dest="style", help="style of music")
	args = parser.parse_args()

	if not os.path.isdir(args.enc_dir):
		print("Enc_dir dir given is not a directory")
		os.exit(1)
	if not os.path.isdir(args.output):
		print("Output dir given is not a directory")
		os.exit(1)

	note_offsets={}
	note_offsets[38]=45
	note_offsets[62]=33
	note_offset = note_offsets[args.note_range]

	(_,_,files) = next(os.walk(args.enc_dir))
	enc_files = [f for f in files if '.txt' in f]

	if not os.path.exists(os.path.join(args.output, args.style)):
		os.makedirs(os.path.join(args.output, args.style))

	for enc_f in enc_files:
		with open(os.path.join(args.enc_dir, enc_f)) as f:
			data = f.read()
			write_mid_mp3_wav(data, enc_f[:-4] + '.mid', args.sample_freq, note_offset, os.path.join(args.output, args.style))

