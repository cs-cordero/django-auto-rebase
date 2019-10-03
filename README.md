# Django Auto Rebase

## What is this?
This is a command-line tool that allows you to rebase a conflicting Django
migration on top of the other Django migration renaming (and renumbering) the
migration filename and also editing the `dependencies` attribute on the
`Migration` class within the file.

## Installation
```bash
$ pip install django-auto-rebase
```

## Usage
```bash
$ dar [app-name] [migration-file-to-be-rebased]
```

## Example Usage
1. First, because you're a good team player, before pushing to your repo, you
   first run makemigrations --dry-run --check to make sure you're not causing
   any migration conflicts
```bash
$ python manage.py makemigrations --dry-run --check
CommandError: Conflicting migrations detected; multiple leaf nodes in the migration graph: (0006_auto_20191002_1512, 0006_auto_20191001_1001 in my_app_name).
To fix them run 'python manage.py makemigrations --merge'
```

2. Uh, oh - looks like we have a merge conflict.  We can fix that!
```bash
$ dar my_app_name 0006_auto_20191002_1512  #  this is the file to be rebased
```

3. End result
    * 0006_auto_20191002_1512.py will be renamed to 0007_auto_20191002_1512.py.
    * 0007_auto_20191002_1512 will depend on 0006_auto_20191001_1001.
    * If you specified the 0006_auto_20191001_1001 file in the command above, the
      reverse would have happened.

## Requirements
* Python 3.7 (for now. file an issue if you need an earlier version supported)
* Django 2.2 (earlier versions will likely work, but it's untested for now.

## Limitations
* Only works on leaf nodes that have migration conflicts.
* Only works on leaf nodes within the same app.

## FAQ
### Is this a Django Command?
No, although this package is tightly coupled to Django, it is NOT a Django
app that you need to add to your `INSTALLED_APPS` or call through a `manage.py`.

### How does it find the root Django path?
The first thing the script does after parsing your arguments is it walks up
the current working directory until it finds the `manage.py` file that most if
not all Django applications have.  The folder that holds the first
`manage.py` directory is appended to `sys.path`.

### Why do you even need this?
Well, you don't really need it, but _I_ find it helpful.

Suppose the migration tree looks like this:
```
0001_xxx <-- 0002_xxx <-- 0003_xxx
```

Then two developers, working in separate branches, generate their own `0004_xxx`
migration.  Once the first developer gets their code merged to master, the
second developer's migration tree is immediately stale/in conflict because
_its_ `0004_xxx` will still be pointing at  `0003_xxx` as a dependency.  You
may find yourself getting this error message:

```
Conflicting migrations detected; multiple leaf nodes in the migration graph:
(0004_xxx, 0004_yyy in my_app_name).
To fix them run 'python manage.py makemigrations --merge'
```

As the message suggests, you could run `makemigrations --merge`, which
generates a new leaf node `0005_xxx` and specifies the two `0004_xxx`
migrations as a dependencies.  This works in small doses, but I'm not a huge fan.
(see below)

### What's wrong with makemigrations --merge?
The magic numbers of each migration starts meaning less and less.

Strictly speaking, they really do mean nothing - Django doesn't care at all
about the number:  A 0004_xxx migration could depend on a migration named
9999_xxx, which depends on 1234_xxx.

Practically speaking, I do find value in seeing the dependency order of the
migration tree follow their actual numbers.  This tool helps rebase two conflicting
migrations with ease.


## Author

[Christopher Sabater Cordero](https://github.com/cs-cordero)
