#!/bin/bash
# Copyright 2023 VMware, Inc.
# SPDX-License-Identifier: MPL-2.0

set -e
source $(dirname "${BASH_SOURCE[0]}")/utils.sh
enable_debugging

printf "%20s\n" "Supported OS"
jq -r '.supported_os[]' $SUPPORTED_CONTEXT_JSON | xargs printf "%20s\n"

echo ""
next_hint_msg "Use \"make run-artifacts-container \" to run the artifacts container."
