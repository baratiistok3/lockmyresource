#!/bin/sh

if lockmyresource --user Locke lock fork1 "Never mind"
then
    echo lock OK
else
    exit 1
fi

if lockmyresource --user Locke list
then
    echo list OK
else
    echo list FAILED
    exit 2
fi

if lockmyresource --user Descartes lock fork1 "In your dreams!"
then
    echo deny lock FAILED
else
    echo deny lock OK
fi

if lockmyresource --user Descartes release fork1
then
    echo deny release FAILED
else
    echo deny release OK
fi

if lockmyresource --user Locke release fork1
then
    echo release OK
else
    echo release FAILED
fi
