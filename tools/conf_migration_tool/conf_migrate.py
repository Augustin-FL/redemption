#!/usr/bin/python3 -O
# -*- coding: utf-8 -*-
##
# Copyright (c) 2021 WALLIX. All rights reserved.
# Licensed computer software. Property of WALLIX.
# Product Name: WALLIX Bastion v9.0
# Author(s): Raphael Zhou
# Module description:  Sesman Worker
##

from collections import OrderedDict
from shutil import copyfile
from enum import Enum, IntEnum
from typing import List, Tuple, Dict, Optional, Union, Iterable, NamedTuple, Generator

import os
import re
import sys
import traceback
import itertools

rgx_version = re.compile(r'^(\d+)\.(\d+)\.(\d+)(.*)')


class RedemptionVersionError(Exception):
    pass


class RedemptionVersion:
    def __init__(self, version: str) -> None:
        m = rgx_version.match(version)
        if m is None:
            raise RedemptionVersionError(
                f"Invalid version string format: {version}")

        self.__major = int(m.group(1))
        self.__minor = int(m.group(2))
        self.__build = int(m.group(3))
        self.__revision = m.group(4)

    def __str__(self) -> str:
        return f"{self.__major}.{self.__minor}.{self.__build}{self.__revision}"

    def __lt__(self, other: 'RedemptionVersion') -> bool:
        return self.__part() < other.__part()

    def __le__(self, other: 'RedemptionVersion') -> bool:
        return self.__part() <= other.__part()

    @staticmethod
    def from_file(filename: str) -> 'RedemptionVersion':
        with open(filename) as f:
            line = f.readline()  # read first line
            items = line.split()
            version_string = items[1]
            return RedemptionVersion(version_string)

    def __part(self) -> Tuple[int, int, int, str]:
        return (self.__major, self.__minor, self.__build, self.__revision)


class ConfigKind(IntEnum):
    Unknown = 0
    NewLine = 1
    Comment = 2
    Section = 3
    KeyValue = 4


rgx_ini_parser = re.compile(
    r'(\n)|'
    r'[ \t]*(#)[^\n]*|'
    r'[ \t]*\[[ \t]*(.+?)[ \t]*\][ \t]*|'
    r'[ \t]*([^\s]+)[ \t]*=[ \t]*(.*?)[ \t]*(?=\n|$)|'
    r'[^\n]+')


novalue = ''


class ConfigurationFragment(NamedTuple):
    text: str
    kind: ConfigKind
    value1: str = novalue
    value2: str = novalue


newline_fragment = ConfigurationFragment('\n', ConfigKind.NewLine)


def _to_fragment(m: re.Match) -> ConfigurationFragment:
    # new line
    if m.start(1) != -1:
        return newline_fragment

    # comment
    if m.start(2) != -1:
        return ConfigurationFragment(
            m.group(0), ConfigKind.Comment
        )

    # section
    if m.start(3) != -1:
        return ConfigurationFragment(
            m.group(0), ConfigKind.Section,
            m.group(3)
        )

    # variable
    if m.start(4) != -1:
        return ConfigurationFragment(
            m.group(0), ConfigKind.KeyValue,
            m.group(4),
            m.group(5),
        )

    return ConfigurationFragment(m.group(0), ConfigKind.Unknown)


ConfigurationFragmentListType = List[ConfigurationFragment]


def parse_configuration(content: str) -> ConfigurationFragmentListType:
    return list(map(_to_fragment, rgx_ini_parser.finditer(content)))


def parse_configuration_from_file(filename: str) -> Tuple[str, ConfigurationFragmentListType]:
    with open(filename, encoding='utf-8') as f:
        content = f.read()
        return (content, parse_configuration(content))


class UpdateItem(NamedTuple):
    section: Optional[str] = None
    key: Optional[str] = None
    values: Optional[Dict[str, str]] = None

    def __call__(self, section: str, key: str, value: str) -> Tuple[str, str, str]:
        if self.section is not None:
            section = self.section
        if self.key is not None:
            key = self.key
        if self.values is not None:
            value = self.values.get(value, value)
        return section, key, value


class RemoveItem:
    pass


class MoveSection(NamedTuple):
    name: str


MigrationKeyOrderType = Union[RemoveItem, UpdateItem]
MigrationSectionOrderType = Union[RemoveItem,
                                  MoveSection,
                                  Dict[str, MigrationKeyOrderType],
                                  Iterable[Union[MoveSection,
                                                 Dict[str, MigrationKeyOrderType]]]]
MigrationDescType = Dict[str, MigrationSectionOrderType]

MigrationType = Tuple[RedemptionVersion, MigrationDescType]


def migration_filter(migration_defs: Iterable[MigrationType],
                     previous_version: RedemptionVersion) -> List[MigrationType]:
    migration_defs = sorted(migration_defs, key=lambda t: t[0])

    for i, t in enumerate(migration_defs):
        if previous_version >= t[0]:
            continue

        return migration_defs[i:]

    return []


def migration_def_to_actions(fragments: Iterable[ConfigurationFragment],
                             migration_def: MigrationDescType
                             ) -> Tuple[
                                 List[Tuple[str, str]],  # renamed_sections
                                 # section, old_key, new_key, new_value
                                 List[Tuple[str, str, str, str]],  # renamed_keys
                                 # old_section, old_key, new_section, new_key, new_value
                                 List[Tuple[str, str, str, str, str]],  # moved_keys
                                 List[str],  # removed_sections
                                 List[Tuple[str, str]],  # removed_keys
                                ]:
    section = ''
    original_section = ''
    migration_key_desc = None
    renamed_sections: List[Tuple[str, str]] = []
    renamed_keys: List[Tuple[str, str, str, str]] = []
    moved_keys: List[Tuple[str, str, str, str, str]] = []
    removed_sections: List[str] = []
    removed_keys: List[Tuple[str, str]] = []

    for fragment in fragments:
        if fragment.kind == ConfigKind.KeyValue:
            if migration_key_desc:
                order = migration_key_desc.get(fragment.value1)
                if order is None:
                    pass
                elif isinstance(order, RemoveItem):
                    removed_keys.append((section, fragment.value1))
                elif isinstance(order, UpdateItem):
                    t = order(section, fragment.value1, fragment.value2)
                    if t[0] == section:
                        renamed_keys.append((original_section, fragment.value1, t[1], t[2]))
                    else:
                        moved_keys.append((original_section, fragment.value1, *t))

        elif fragment.kind == ConfigKind.Section:
            migration_key_desc = None
            section = fragment.value1
            original_section = section
            order = migration_def.get(section)

            if order is None:
                pass
            elif isinstance(order, RemoveItem):
                removed_sections.append(section)
            elif isinstance(order, MoveSection):
                renamed_sections.append((section, order.name))
            elif isinstance(order, dict):
                migration_key_desc = order
            else:
                for order in order:
                    if isinstance(order, MoveSection):
                        renamed_sections.append((section, order.name))
                        section = order.name
                    else:
                        migration_key_desc = order

    return renamed_sections, renamed_keys, moved_keys, removed_sections, removed_keys


def fragments_to_spans_of_sections(fragments: Iterable[ConfigurationFragment]) -> Dict[str, List[Tuple[int, int]]]:
    start = 0
    section = ''
    section_spans: Dict[str, List[Tuple[int, int]]] = dict()

    i = 0
    for i, fragment in enumerate(fragments):
        if fragment.kind == ConfigKind.Section:
            if start < i-1:
                section_spans.setdefault(section, []).append((start, i-1))
            section = fragment.value1
            start = i
    if start < i-1:
        section_spans.setdefault(section, []).append((start, i-1))

    return section_spans


def migrate(fragments: List[ConfigurationFragment],
            migration_def: MigrationDescType) -> Tuple[bool, List[ConfigurationFragment]]:
    renamed_sections, renamed_keys, moved_keys, removed_sections, removed_keys \
        = migration_def_to_actions(fragments, migration_def)

    if not (renamed_sections or renamed_keys or moved_keys or removed_sections or removed_keys):
        return (False, fragments)

    reinject_fragments: Dict[int, Iterable[ConfigurationFragment]] = dict()
    section_spans = fragments_to_spans_of_sections(fragments)

    def iter_from_spans(spans) -> Iterable[int]:
        return (i for span in spans for i in range(span[0], span[1]))

    def iter_key_fragment(section_name: str,
                          kind: ConfigKind,
                          key_name: str
                          ) -> Generator[Tuple[int, ConfigurationFragment], None, None]:
        for i in iter_from_spans(section_spans.get(section_name, ())):
            fragment: ConfigurationFragment = fragments[i]
            if fragment.kind != ConfigKind.KeyValue or key_name != fragment.value1:
                continue
            yield i, fragment

    for section, old_key, new_key, new_value in renamed_keys:
        for i, fragment in iter_key_fragment(section, ConfigKind.KeyValue, old_key):
            reinject_fragments[i] = (
                ConfigurationFragment(f'#{fragment.text}', ConfigKind.Comment),
                newline_fragment,
                ConfigurationFragment(f'{new_key}={new_value}', ConfigKind.KeyValue,
                                      new_key, new_value),
            )

    for section in removed_sections:
        for i in iter_from_spans(section_spans.get(section, ())):
            fragment = fragments[i]
            if fragment.kind in (ConfigKind.KeyValue, ConfigKind.Section):
                # if fragment.kind == ConfigKind.Section:
                #     del section_spans[section]
                reinject_fragments[i] = (
                    ConfigurationFragment(f'#{fragment.text}', ConfigKind.Comment),)

    for t in itertools.chain(removed_keys, moved_keys):
        for i, fragment in iter_key_fragment(t[0], ConfigKind.KeyValue, t[1]):
            reinject_fragments[i] = (
                ConfigurationFragment(f'#{fragment.text}', ConfigKind.Comment),)

    for old_section, new_section in renamed_sections:
        spans = section_spans.get(old_section, ())
        if spans:
            for istart, _ in spans:
                reinject_fragments[istart] = (
                    ConfigurationFragment(f'#{fragments[istart].text}', ConfigKind.Comment),
                    newline_fragment,
                    ConfigurationFragment(f'[{new_section}]', ConfigKind.Section, new_section),
                )

    added_keys: Dict[str, List[ConfigurationFragment]] = dict()

    for old_section, old_key, new_section, new_key, new_value in moved_keys:
        for _ in iter_key_fragment(old_section, ConfigKind.KeyValue, old_key):
            added_keys.setdefault(new_section, []).extend((
                newline_fragment,
                ConfigurationFragment(f'{new_key}={new_value}', ConfigKind.KeyValue,
                                      new_key, new_value),
                newline_fragment,
            ))

    result_fragments: List[ConfigurationFragment] = []

    # insert a key in a section
    for i, fragment in enumerate(fragments):
        added_fragments = reinject_fragments.get(i, (fragment,))

        section = None
        for x in added_fragments:
            if x.kind == ConfigKind.Section:
                section = x.value1
                break

        result_fragments.extend(added_fragments)
        if section:
            key = added_keys.get(section)
            if key:
                result_fragments.extend(key)
                added_keys[section] = []

    # add new section
    for section, keys in added_keys.items():
        if keys:
            result_fragments.extend((
                newline_fragment,
                ConfigurationFragment(f'[{section}]', ConfigKind.Section, section),
            ))
            result_fragments.extend(keys)

    return (True, result_fragments)


migration_defs: List[MigrationType] = [
    (RedemptionVersion('9.1.39'), {
        'globals': {
            'session_timeout': UpdateItem(key='base_inactivity_timeout'),
        },
    }),
    (RedemptionVersion("9.1.71"), {
        'rdp': dict(itertools.chain(
            (
                (key, UpdateItem(section='session_probe', key=key[14:]))
                for key in ('session_probe_exe_or_file',
                            'session_probe_arguments',
                            'session_probe_customize_executable_name',
                            'session_probe_allow_multiple_handshake',
                            'session_probe_at_end_of_session_freeze_connection_and_wait',
                            'session_probe_enable_cleaner',
                            'session_probe_clipboard_based_launcher_reset_keyboard_status',)
            ),
            (
                ('session_probe_bestsafe_integration', UpdateItem(section='session_probe',
                                                                   key='enable_bestsafe_interaction')),
            )
        )),
        'video': {
            'replay_path': UpdateItem(section='mod_replay'),
        },
    }),
    (RedemptionVersion("9.1.76"), {
        'all_target_mod': {
            'connection_retry_count': RemoveItem(),
        },
    }),
]


def migrate_file(version: RedemptionVersion,
                 ini_filename: str,
                 temporary_ini_filename: str,
                 saved_ini_filename: str,
                 ) -> bool:
    _, fragments = parse_configuration_from_file(ini_filename)

    is_changed = False
    for _, desc in migration_filter(migration_defs, version):
        is_updated, fragments = migrate(fragments, desc)
        is_changed = is_changed or is_updated

    if is_changed:
        with open(temporary_ini_filename, 'w', encoding='utf-8') as f:
            f.write(''.join(fragment.text for fragment in fragments))

        copyfile(ini_filename, saved_ini_filename)

        os.rename(temporary_ini_filename, ini_filename)

    return is_changed


if __name__ == '__main__':
    if len(sys.argv) != 4 or sys.argv[1] not in ('-s', '-f'):
        print(f'{sys.argv[0]} {{-s|-f}} version ini_filename\n'
              '  -s   <version> is a output format of redemption --version\n'
              '  -f   <version> is a version of redemption from file',
              file=sys.stderr)
        exit(1)

    ini_filename = sys.argv[3]
    if sys.argv[1] == '-f':
        old_version = RedemptionVersion.from_file(sys.argv[2])
    else:
        old_version = RedemptionVersion(sys.argv[2])

    print(f"PreviousRedemptionVersion={old_version}")

    if migrate_file(old_version,
                    ini_filename=ini_filename,
                    temporary_ini_filename=f'{ini_filename}.work',
                    saved_ini_filename=f'{ini_filename}.{old_version}'):
        print("Configuration file updated")
