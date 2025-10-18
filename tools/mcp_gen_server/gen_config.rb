#!/usr/bin/env ruby
# frozen_string_literal: true

# SPDX-License-Identifier: BSD-3-Clause-Clear
# Copyright (c) 2025 RISC-V International

# Generate a CPU configuration
# Usage: ruby gen_config.rb <config_name>

require "pathname"

if ARGV.length != 1
  STDERR.puts "Usage: #{$0} <config_name>"
  exit 1
end

config_name = ARGV[0]

# Get repo root (two levels up from this script)
script_dir = Pathname.new(__FILE__).dirname
repo_root = script_dir.parent.parent

# Add lib to load path
$LOAD_PATH.unshift(repo_root / "tools/ruby-gems/udb/lib")

begin
  require "udb/resolver"

  puts "Generating config '#{config_name}'..."
  resolver = Udb::Resolver.new(repo_root)
  cfg_arch = resolver.cfg_arch_for(config_name)

  puts "Successfully generated: #{cfg_arch.name}"
  puts "Location: #{repo_root}/gen/arch/#{config_name}/"
rescue LoadError => e
  STDERR.puts "ERROR: Failed to load UDB library"
  STDERR.puts "#{e.message}"
  STDERR.puts ""
  STDERR.puts "Try running: bundle install"
  exit 1
rescue StandardError => e
  STDERR.puts "ERROR: Failed to generate config '#{config_name}'"
  STDERR.puts "#{e.class}: #{e.message}"
  STDERR.puts e.backtrace.join("\n") if ENV["DEBUG"]
  exit 1
end
