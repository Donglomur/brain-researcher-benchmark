function out = ccep_project_native_metadata(meta, recordingKey, sourceManifestSha256)
% Original prospective CCEP metadata projection; no waveform loading or scoring.
% Caller obtains meta using the pinned read_mef_session_metadata(...,[],true,false).
% This function does not authenticate a native binary or its claimed inputs.
% Output and the source manifest are operator-private. Never expose them to agents.
    assert(isstruct(meta) && isscalar(meta));
    out.schema = 'clinical-ccep-native-metadata-v1';
    out.reader_commit = 'c896ca41b28f2af927836d18b0afc8ba719b8d57';
    out.recording_key = textvalue(recordingKey, 128);
    out.source_manifest_sha256 = textvalue(sourceManifestSha256, 64);
    assert(~isempty(regexp(out.source_manifest_sha256, '^[0-9a-f]{64}$', 'once')));
    rejectrecords(meta);
    out.number_of_time_series_channels = integertext(meta.number_of_time_series_channels, 'int32');
    out.number_of_video_channels = integertext(meta.number_of_video_channels, 'int32');
    channels = meta.time_series_channels;
    assert((isstruct(channels) && (isvector(channels) || isempty(channels))) || ...
           (isa(channels, 'double') && isempty(channels)));
    assert(int64(numel(channels)) == int64(meta.number_of_time_series_channels));
    out.channels = cell(1, numel(channels));
    for c = 1:numel(channels)
        ch = channels(c);
        rejectrecords(ch);
        item.native_name = textvalue(ch.name, 512);
        item.number_of_segments = integertext(ch.number_of_segments, 'int64');
        item.earliest_start_time = integertext(ch.earliest_start_time, 'int64');
        item.latest_end_time = integertext(ch.latest_end_time, 'int64');
        item.metadata = section2(ch.metadata.section_2);
        segments = ch.segments;
        assert((isstruct(segments) && (isvector(segments) || isempty(segments))) || ...
               (isa(segments, 'double') && isempty(segments)));
        assert(int64(numel(segments)) == ch.number_of_segments);
        item.segments = cell(1, numel(segments));
        for s = 1:numel(segments)
            seg = segments(s);
            rejectrecords(seg);
            part.metadata = section2(seg.metadata.section_2);
            indices = seg.time_series_indices;
            assert((isstruct(indices) && (isvector(indices) || isempty(indices))) || ...
                   (isa(indices, 'double') && isempty(indices)));
            assert(int64(numel(indices)) == seg.metadata.section_2.number_of_blocks);
            part.indices = cell(1, numel(indices));
            for b = 1:numel(indices)
                idx = indices(b);
                block.start_sample = integertext(idx.start_sample, 'int64');
                block.start_time = integertext(idx.start_time, 'int64');
                block.number_of_samples = integertext(idx.number_of_samples, 'uint32');
                block.RED_block_flags = integertext(idx.RED_block_flags, 'uint8');
                part.indices{b} = block;
            end
            item.segments{s} = part;
        end
        out.channels{c} = item;
    end
end

function out = section2(md)
    ints = {'acquisition_channel_number', 'start_sample', 'number_of_samples', ...
            'number_of_blocks', 'number_of_discontinuities'};
    for k = 1:numel(ints)
        out.(ints{k}) = integertext(md.(ints{k}), 'int64');
    end
    floats = {'sampling_frequency', 'units_conversion_factor', ...
              'low_frequency_filter_setting', 'high_frequency_filter_setting', ...
              'notch_filter_frequency_setting', 'AC_line_frequency'};
    for k = 1:numel(floats)
        val = md.(floats{k});
        assert(isa(val, 'double') && isreal(val) && isscalar(val));
        % num2hex preserves all binary64 bits, including sentinels and signed zero.
        out.([floats{k}, '_hex']) = lower(num2hex(val));
    end
    out.units_description = textvalue(md.units_description, 512);
end

function rejectrecords(value)
    assert(~isfield(value, 'records') || isempty(value.records), ...
           'Records must be disabled before metadata projection.');
end

function out = textvalue(value, maxchars)
    assert(ischar(value) && (isrow(value) || isempty(value)));
    assert(numel(value) <= maxchars);
    out = value;
end

function out = integertext(value, expectedClass)
    % Never pass sample/time identities through double, sprintf or JSON numbers.
    assert(isa(value, expectedClass) && isreal(value) && isscalar(value));
    signed = int64(value); % Selected unsigned source types are at most uint32.
    negative = signed < int64(0);
    if negative
        magnitude = uint64(-(signed + int64(1))) + uint64(1);
    else
        magnitude = uint64(signed);
    end
    out = '';
    ten = uint64(10);
    while magnitude ~= uint64(0)
        digit = rem(magnitude, ten);
        out = [char(uint8(48) + uint8(digit)), out]; %#ok<AGROW>
        magnitude = idivide(magnitude, ten, 'floor');
    end
    if isempty(out), out = '0'; end
    if negative, out = ['-', out]; end
end
