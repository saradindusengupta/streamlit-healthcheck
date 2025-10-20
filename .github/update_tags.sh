#!/bin/bash

# Script to bump MINOR or MAJOR version in semver based on latest git tag with prefix 'v'
# Usage: Run and choose which version to bump (MINOR or MAJOR)

set -e

# Fetch latest tags
git fetch --tags

# Get latest tag with prefix 'v'
latest_tag=$(git tag --list 'v*' --sort=-v:refname | head -n 1)

if [[ -z "$latest_tag" ]]; then
	echo "No tags found with prefix 'v'. Starting from v0.0.0."
	latest_tag="v0.0.0"
fi

# Remove 'v' prefix
version=${latest_tag#v}

# Split version into components
IFS='.' read -r major minor patch <<< "$version"

echo "Current version: v$major.$minor.$patch"

echo "What do you want to bump?"
echo "1) MINOR"
echo "2) MAJOR"
read -rp "Enter 1 or 2: " bump_choice

case "$bump_choice" in
	1)
		minor=$((minor + 1))
		patch=0
		;;
	2)
		major=$((major + 1))
		minor=0
		patch=0
		;;
	*)
		echo "Invalid input. Please enter 1 for MINOR or 2 for MAJOR."
		exit 1
		;;
esac

new_version="v$major.$minor.$patch"
echo "New version: $new_version"

# Create and push new tag
git tag "$new_version"
git push origin "$new_version"
echo "Tag $new_version pushed to origin."
