#!/usr/bin/env python3
"""Exact conditional reconstruction from the declared fixed-map participant packet.

For one family/task stratum, let n be the eligible population, r a row
margin and c a category margin. Independently permuting both labels has
the same overlap distribution as fixing one label and uniformly permuting
the other: Hypergeometric(n, r, c). Its mean is r*c/n and its variance is
r*c*(n-r)*(n-c)/(n*n*(n-1)). Independent strata contribute additive
moments. No independence across cells, families or deletion cases is used.

Only the input named by --packet is read. --output - streams JSONL to stdout;
an ordinary output path is created exclusively. Compatible with Python 3.11/3.12.
"""

import argparse
from contextlib import contextmanager
from dataclasses import dataclass, field
from fractions import Fraction
import hashlib
import json
import sys


PACKET_SCHEMA = "PFC_FULL99_FIXED_MAP_PACKET_V1"
OUTPUT_SCHEMA = "PFC_CONDITIONAL_CASES_V1"
CATEGORIES = 8
MAX_OUTPUT_BYTES = 128 * 1024 * 1024
ZERO = Fraction(0, 1)


class PacketError(ValueError):
    """The packet does not satisfy the declared participant schema."""


def require(condition, message):
    if not condition:
        raise PacketError(message)


def is_integer(value):
    # JSON booleans are not integer indices, despite Python's subclassing.
    return type(value) is int


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise PacketError("Duplicate JSON object member")
        result[key] = value
    return result


def reject_constant(_value):
    raise PacketError("Nonfinite JSON numbers are not permitted")


def string_array(value, name):
    require(isinstance(value, list), name + " must be an array")
    require(all(isinstance(item, str) for item in value),
            name + " must contain strings")
    require(len(set(value)) == len(value), name + " must be unique")
    return value


def validate_packet(packet, *, fixed_dimensions=True):
    """Validate computation inputs; the CLI always requires the full contract.

    fixed_dimensions=False exists only for separately authored, invented
    source controls. It is not exposed as a participant command-line option.
    Contexts and diagnostic metadata do not enter the requested moments.
    """
    require(isinstance(packet, dict), "Packet must be an object")
    require(packet.get("schema") == PACKET_SCHEMA, "Wrong packet schema")
    animals = string_array(packet.get("animals"), "animals")
    families = packet.get("families")
    records = packet.get("records")
    units = packet.get("units")
    contexts = packet.get("contexts")
    require(isinstance(families, list), "families must be an array")
    require(isinstance(records, list), "records must be an array")
    require(isinstance(units, list), "units must be an array")
    require(isinstance(contexts, list), "contexts must be an array")
    if fixed_dimensions:
        require(len(animals) == 68, "Expected 68 animals")
        require(len(families) == 12, "Expected 12 families")
        require(len(records) == 99, "Expected 99 recordings")
        require(len(units) == 19186, "Expected 19186 fitting units")
        require(len(contexts) == 16, "Expected 16 fixed contexts")

    family_keys = set()
    row_counts = []
    for family in families:
        require(isinstance(family, dict), "Family must be an object")
        key = family.get("key")
        require(isinstance(key, str), "Family key must be a string")
        require(key not in family_keys, "Family keys must be unique")
        family_keys.add(key)
        labels = string_array(family.get("labels"), "family labels")
        row_counts.append(len(labels))

    animal_set = set(animals)
    recording_map = {}
    for record in records:
        require(isinstance(record, dict), "Recording must be an object")
        recording = record.get("id")
        animal = record.get("animal")
        task = record.get("task")
        require(isinstance(recording, str), "Recording ID must be a string")
        require(recording not in recording_map, "Duplicate recording ID")
        # A declared recording may have zero fitting units and therefore an
        # animal absent from the fitting-animal roster. Units are checked below.
        require(isinstance(animal, str) and bool(animal),
                "Recording animal must be a nonempty string")
        require(isinstance(task, str), "Recording task must be a string")
        recording_map[recording] = (animal, task)

    seen_ids = set()
    for unit in units:
        require(isinstance(unit, dict), "Unit must be an object")
        unit_id = unit.get("id")
        recording = unit.get("recording")
        animal = unit.get("animal")
        task = unit.get("task")
        category = unit.get("category")
        labels = unit.get("labels")
        require(isinstance(unit_id, str), "Unit ID must be a string")
        require(unit_id not in seen_ids, "Duplicate unit ID")
        seen_ids.add(unit_id)
        require(isinstance(recording, str) and recording in recording_map,
                "Unit recording is not declared")
        require(isinstance(animal, str) and animal in animal_set,
                "Unit animal is not in the roster")
        require(isinstance(task, str), "Unit task must be a string")
        require(recording_map[recording] == (animal, task),
                "Unit and recording animal/task disagree")
        require(is_integer(category) and 0 <= category < CATEGORIES,
                "Unit category must be an integer from 0 through 7")
        require(isinstance(labels, list) and len(labels) == len(families),
                "Unit must have one label slot per family")
        for family_index, label in enumerate(labels):
            require(is_integer(label), "Family label index must be an integer")
            require(label == -1 or 0 <= label < row_counts[family_index],
                    "Family label index is outside its declared axis")


@dataclass(slots=True)
class Margins:
    n: int = 0
    rows: dict = field(default_factory=dict)
    categories: list = field(default_factory=lambda: [0] * CATEGORIES)

    def add(self, row, category):
        self.n += 1
        self.rows[row] = self.rows.get(row, 0) + 1
        self.categories[category] += 1


def cell_moments(n, r, c):
    """Return exact moments, including empty and singleton strata."""
    if n == 0 or r == 0 or c == 0:
        return ZERO, ZERO
    mean = Fraction(r * c, n)
    if n == 1 or r == n or c == n:
        return mean, ZERO
    variance = Fraction(r * c * (n - r) * (n - c), n * n * (n - 1))
    return mean, variance


def rational_matrix(matrix):
    return [[[value.numerator, value.denominator] for value in row]
            for row in matrix]


class Reconstruction:
    """Store full and per-animal sufficient statistics, never saved answers."""

    def __init__(self, packet, *, fixed_dimensions=True):
        validate_packet(packet, fixed_dimensions=fixed_dimensions)
        self.animals = packet["animals"]
        self.families = packet["families"]
        family_count = len(self.families)
        self.counts = [[[0] * CATEGORIES for _ in family["labels"]]
                       for family in self.families]
        self.margins = [{} for _ in self.families]
        self.animal_counts = [[{} for _ in range(family_count)]
                              for _ in self.animals]
        self.animal_margins = [[{} for _ in range(family_count)]
                               for _ in self.animals]
        animal_indices = {animal: index
                          for index, animal in enumerate(self.animals)}

        for unit in packet["units"]:
            animal_index = animal_indices[unit["animal"]]
            task = unit["task"]
            category = unit["category"]
            for family_index, row in enumerate(unit["labels"]):
                if row == -1:
                    continue
                self.counts[family_index][row][category] += 1
                full_tasks = self.margins[family_index]
                if task not in full_tasks:
                    full_tasks[task] = Margins()
                full_tasks[task].add(row, category)

                animal_tasks = self.animal_margins[animal_index][family_index]
                if task not in animal_tasks:
                    animal_tasks[task] = Margins()
                animal_tasks[task].add(row, category)
                animal_cells = self.animal_counts[animal_index][family_index]
                cell = (row, category)
                animal_cells[cell] = animal_cells.get(cell, 0) + 1

    def case(self, animal_index=None):
        """Build one complete case, recomputing moments after any deletion."""
        case_key = ("full" if animal_index is None else
                    "without:" + self.animals[animal_index])
        output_families = []
        for family_index, family in enumerate(self.families):
            counts = [row.copy() for row in self.counts[family_index]]
            means = [[ZERO] * CATEGORIES for _ in family["labels"]]
            variances = [[ZERO] * CATEGORIES for _ in family["labels"]]
            removed_tasks = {}
            if animal_index is not None:
                removed_tasks = self.animal_margins[animal_index][family_index]
                removed_cells = self.animal_counts[animal_index][family_index]
                for (row, category), removed in removed_cells.items():
                    counts[row][category] -= removed

            for task, full in self.margins[family_index].items():
                removed = removed_tasks.get(task)
                n = full.n - (removed.n if removed is not None else 0)
                if n == 0:
                    # The original output axes still exist in the zero matrices.
                    continue
                categories = [full.categories[category] -
                              (removed.categories[category]
                               if removed is not None else 0)
                              for category in range(CATEGORIES)]
                for row, original_r in full.rows.items():
                    r = original_r - (removed.rows.get(row, 0)
                                      if removed is not None else 0)
                    if r == 0:
                        continue
                    for category, c in enumerate(categories):
                        if c == 0:
                            continue
                        mean, variance = cell_moments(n, r, c)
                        means[row][category] += mean
                        variances[row][category] += variance

            output_families.append({
                "key": family["key"],
                "counts": counts,
                "mean": rational_matrix(means),
                "variance": rational_matrix(variances),
            })
        return {"case": case_key, "families": output_families}


@contextmanager
def submission_output(output_path):
    if output_path == "-":
        # Real interpreter stdout supports reconfigure. In-memory source
        # controls may supply an already-Unicode text stream instead.
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="strict", newline="\n")
        yield sys.stdout
        sys.stdout.flush()
    else:
        # Exclusive creation refuses pre-existing files and symlinks. A later
        # write failure leaves a partial output for diagnosis and is not retried.
        with open(output_path, "x", encoding="utf-8", newline="\n") as output:
            yield output


def write_jsonl(reconstruction, packet_sha256, output):
    case_keys = ["full"] + ["without:" + animal
                            for animal in reconstruction.animals]
    encoder = json.JSONEncoder(ensure_ascii=False, allow_nan=False,
                               separators=(",", ":"))
    written_bytes = 0

    def write_line(value):
        nonlocal written_bytes
        # Keep only one serialized line at a time and check its exact UTF-8
        # byte count before writing. No progress text is written to stdout.
        line = encoder.encode(value) + "\n"
        line_bytes = len(line.encode("utf-8"))
        if written_bytes + line_bytes > MAX_OUTPUT_BYTES:
            raise PacketError("Submission exceeds the 128 MiB output limit")
        output.write(line)
        written_bytes += line_bytes

    write_line({"schema": OUTPUT_SCHEMA,
                "packet_sha256": packet_sha256,
                "cases": case_keys})
    for animal_index in [None] + list(range(len(reconstruction.animals))):
        write_line(reconstruction.case(animal_index))


def write_submission(packet_path, output_path):
    with open(packet_path, "rb") as packet_file:
        original_bytes = packet_file.read()
    packet_sha256 = hashlib.sha256(original_bytes).hexdigest()
    packet = json.loads(original_bytes.decode("utf-8"),
                        object_pairs_hook=unique_object,
                        parse_constant=reject_constant)
    reconstruction = Reconstruction(packet)
    # The aggregation retains no unit list. Release the original JSON payload
    # before allocating case matrices. Never retain all 69 output cases.
    del packet, original_bytes
    with submission_output(output_path) as output:
        write_jsonl(reconstruction, packet_sha256, output)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", required=True)
    parser.add_argument("--output", required=True)
    arguments = parser.parse_args(argv)
    try:
        write_submission(arguments.packet, arguments.output)
    except (OSError, ValueError, TypeError) as exc:
        # Keep diagnostics bounded; all scientific output goes to the file.
        print("solution.py: " + str(exc)[:2000], file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
