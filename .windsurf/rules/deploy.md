---
trigger: manual
description:
globs:
---
deploying process:
1. commit the changes 
2. push to github
3. push to heroku
4. view the logs on heroku: there should be a successful build and passed tests (remember that "heroku logs --tail" doesnt exit in heroku like regular tail - so use a timeout in the command)
5. fix the issues and repeat the process