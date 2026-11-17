"""Source and complete condition census, never additional canonical tasks."""
PERSONS=("YAC","YAG","YAK","YDG","YDR","YFR","YFS","YHS","YIS","YLS","YMD","YMS","YRH","YRK","YRP","YSD","YSL","YTL")
CONDITIONS=("NR","TSR");COUNTS={"NR":349,"TSR":390};BANDS=("t1","t2","a1","a2","b1","b2","g1","g2")
BAND_HZ=((4,6),(6.5,8),(8.5,10),(10.5,13),(13.5,18),(18.5,30),(30.5,40),(40,49.5))
CONTEXTS=("FFD","TRT","GD","GPT","SFD");REPRESENTATIONS=("released_summary","band_spatial","cleaned_waveform","raw_waveform");MODES=("frozen_program","case_adaptive")
ARMS={"NEURAL-085":("TEXT","GAZE","EEG","TEXT_GAZE","JOINT","NUISANCE","NTG","NTGE","NTG_SHUFFLED_E"),"NEURAL-086":("COVARIATES","PLUS_EEG","COVARIATES_SHUFFLED_E")}
GAZE=("FFD","GD","GPT","TRT","nFixations","meanPupilSize")
NUMERIC=("word_chars","word_position_fraction","previous_word_chars","next_word_chars","sentence_words","sentence_mean_word_chars","sentence_type_token_ratio","train_word_logcount","train_word_oov","sentence_train_unigram_surprisal","FFD_ms","GD_ms","GPT_ms","TRT_ms","nFixations","meanPupilSize","window_pupilSize","omissionRate","sentence_duration_seconds")
BASE_NAMES=NUMERIC+tuple("missing_"+x for x in NUMERIC)+tuple("missing_EEG_"+b for b in BANDS)
INFORMATION_SET="offline_case_local";GATES=tuple(f"G{i:02d}" for i in range(1,29));SEED=0
