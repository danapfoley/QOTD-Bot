# QOTD Bot

This is a Slack bot that automates the process of submitting "Questions Of The Day" to users in a public channel. Currently deployed in Soartech's channel, #qotd. 

It is capable of taking in user-submitted questions with answers, comparing those answers to user attempts, and keeping track of scores for correct answers.

In a public channel, call the bot with @qotd\_bot at the beginning of your message (commands don't use "/"). Alternatively, you can start a private chat with the bot and just talk to it directly, without "@qotd\_bot". Some commands like `answer` are not permitted to run in a public channel.
If you're ever lost, say "@qotd\_bot help" for a list of commands, or contact me directly.

Additionally, if you encounter any bugs or have any feature requests, feel free to either contact me about it, post in #qotd or #qotd-public-test, or submit an issue on GitLab.

## Commands

`add-point(s) [@ user] <# points>` - gives `# points` to `@ user` if specified, 1 point by default

`answer [identifier] [your answer]` - Must be used in a private channel. Checks your `answer` for the corresponding question.

`expire-old-questions` - removes all questions published more than 18 hours ago

`hello` - says hi back and some basic information

`my-questions` - prints a list of your questions, published or not

`old-questions` - gets a list of questions that were expired in the last 24 hours

`poll [identifier] [question] : [option 1] : [option 2] : ...` - creates a poll with a reference tag `identifier`.

`poll [identifier] remove` - removes the poll with the corresponding ID.

`poll [identifier] votes` - shows current vote counts for a poll.

`polls` - prints a list of the currently active polls

`publish <identifier>` - publishes the corresponding question if `identifier` given. Publishes all of your questions otherwise.

`publish-poll [identifier]` - publishes your poll with the specified identifier

`question [identifier] [question] : <answer>` - creates a question with a reference tag `identifier`.

`question [identifier] count` - shows stats on who has answered/guessed a question.

`question [identifier] remove` - removes the question with the corresponding ID.

`questions` - prints a list of today's published questions

`remove [identifier]` removes the question with the corresponding ID

`scores <@ user>` - prints a list of today's scores and running totals, for `<@ user>` if given, for everyone otherwise

`scores-unranked` - prints a list of today's scores and running totals, sorted alphabetically instead of by ranking

`vote [identifier] [option-number]` - votes on a poll. Use option IDs, not the option's text