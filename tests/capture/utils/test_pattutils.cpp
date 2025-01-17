/*
    This program is free software; you can redistribute it and/or modify it
     under the terms of the GNU General Public License as published by the
     Free Software Foundation; either version 2 of the License, or (at your
     option) any later version.

    This program is distributed in the hope that it will be useful, but
     WITHOUT ANY WARRANTY; without even the implied warranty of
     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General
     Public License for more details.

    You should have received a copy of the GNU General Public License along
     with this program; if not, write to the Free Software Foundation, Inc.,
     675 Mass Ave, Cambridge, MA 02139, USA.

    Product name: redemption, a FLOSS RDP proxy
    Copyright (C) Wallix 2014
    Author(s): Christophe Grosjean, Raphael Zhou, Jonathan Poelen
*/

#include "test_only/test_framework/redemption_unit_tests.hpp"

#include "capture/utils/pattutils.hpp"

RED_AUTO_TEST_CASE(TestKbdPattern)
{
    RED_CHECK(!contains_kbd_pattern(""_av));

    RED_CHECK(!contains_kbd_pattern("AT"_av));

    RED_CHECK(!contains_kbd_pattern("Bloc-notes"_av));

    RED_CHECK(contains_kbd_pattern("$kbd:gpedit"_av));

    RED_CHECK(contains_kbd_pattern(" $kbd:gpedit\x01" "AT"_av));

    RED_CHECK(contains_kbd_pattern(" $kbd:kill\x01 " "AT "_av));

    RED_CHECK(contains_kbd_pattern("AT\x01$kbd:kill"_av));

    RED_CHECK(!contains_kbd_pattern("$ocr:Bloc-notes"_av));

    RED_CHECK(contains_kbd_pattern("$ocr-kbd:cmd"_av));

    RED_CHECK(contains_kbd_pattern("$kbd-ocr:cmd"_av));

    RED_CHECK(contains_kbd_pattern("$exact-content,kbd-ocr:cmd"_av));

    RED_CHECK(!contains_kbd_pattern("$content,ocr:cmd"_av));
}

RED_AUTO_TEST_CASE(TestOcrPattern)
{
    RED_CHECK(!contains_ocr_pattern(""_av));

    RED_CHECK(contains_ocr_pattern("AT"_av));

    RED_CHECK(contains_ocr_pattern("Bloc-notes"_av));

    RED_CHECK(contains_ocr_pattern("$ocr:Bloc-notes"_av));

    RED_CHECK(contains_ocr_pattern("$ocr:Bloc-notes\x01" "AT"_av));

    RED_CHECK(contains_ocr_pattern("$kbd:kill\x01" " AT"_av));

    RED_CHECK(contains_ocr_pattern(" AT\x01$kbd:kill"_av));

    RED_CHECK(!contains_ocr_pattern("$kbd:kill"_av));

    RED_CHECK(contains_ocr_pattern("$ocr-kbd:cmd"_av));

    RED_CHECK(contains_ocr_pattern("$kbd-ocr:cmd"_av));

    RED_CHECK(contains_ocr_pattern("$exact-regex,kbd-ocr:cmd"_av));

    RED_CHECK(contains_ocr_pattern("$content,ocr:cmd"_av));
}

RED_AUTO_TEST_CASE(TestKbdOrOcrPattern)
{
    RED_CHECK(!contains_kbd_or_ocr_pattern(""_av));

    RED_CHECK(contains_kbd_or_ocr_pattern("AT"_av));

    RED_CHECK(contains_kbd_or_ocr_pattern("Bloc-notes"_av));

    RED_CHECK(contains_kbd_or_ocr_pattern("$kbd:gpedit"_av));

    RED_CHECK(contains_kbd_or_ocr_pattern(" $kbd:gpedit\x01" "AT"_av));

    RED_CHECK(contains_kbd_or_ocr_pattern(" $kbd:kill\x01 " "AT "_av));

    RED_CHECK(contains_kbd_or_ocr_pattern("AT\x01$kbd:kill"_av));

    RED_CHECK(contains_kbd_or_ocr_pattern("$ocr:Bloc-notes"_av));

    RED_CHECK(contains_kbd_or_ocr_pattern("$ocr-kbd:cmd"_av));

    RED_CHECK(contains_kbd_or_ocr_pattern("$kbd-ocr:cmd"_av));

    // invalid "ocm" rule
    RED_CHECK(!contains_kbd_or_ocr_pattern("$ocm:10.10.46.0/24:3389"_av));

    RED_CHECK(contains_kbd_or_ocr_pattern("$content,kbd-ocr:cmd"_av));

    RED_CHECK(contains_kbd_or_ocr_pattern("$content,ocr:cmd"_av));
}
