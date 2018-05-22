# QOTD Bot

This is a Slack bot that automates the process of submitting "Questions Of The Day" to users in a public channel. Currently deployed in SoarTech's channel, #qotd. There is an additional channel, #qotd-points, where new points earned for questions are announced in realtime.

It is capable of taking in user-submitted questions with answers, comparing those answers to user attempts, and keeping track of scores for correct answers. It also handles polls, which any user is capable of making or voting on.

In a public channel, call the bot with @qotd\_bot at the beginning of your message (commands don't use "/"). Alternatively, you can start a private chat with the bot and just talk to it directly, without "@qotd\_bot" at the beginning of your message. Some commands like `answer` are not permitted to run in a public channel.
If you're ever lost, say "@qotd\_bot help" for a list of commands, or contact me directly.

Additionally, if you encounter any bugs or have any feature requests, feel free to either contact me about it, post in #qotd, or submit an issue on GitLab.

## Commands

### Questions and Answers:

   `add-answer  [identifier] [new answer]` - adds a new possible answer for the question with the corresponding identifier.

   `add-answers [identifier] [new answer 1] : <new answer 2> : ...` - adds multiple new answers for the question with the corresponding identifier

   `answer [identifier] [your answer]` - Must be used in a private channel. Checks your `answer` for the corresponding question.
   
   `approve [@ user] [question ID]` - awards a point for a user on a question of yours.

   `expire-old-questions` - removes all questions published more than 18 hours ago

   `my-questions` - prints a list of your questions, published or not

   `old-questions` - gets a list of questions that were expired in the last 24 hours

   `publish <identifier>` - publishes the corresponding question if `identifier` given. Publishes all of your questions otherwise.

   `question [identifier] [question] : <answer1> : <answer2> : ...` - creates a question with a reference tag `identifier`.

   `question [identifier] remove` - removes the question with the corresponding ID.

   `question [identifier] count` - shows stats on who has answered/guessed a question.

   `questions-remaining` - Prints a list of questions that you have yet to answer or use all your guesses on

   `questions` - prints a list of today's published questions

   `remove [identifier]` removes the question with the corresponding ID

   `remove-answer [identifier] [existing answer]` - removes an answer option from a question. Must be matched _exactly_ to work



### Polls:

   `poll [identifier] [question] : [option 1] : [option 2] : ...` - creates a poll with a reference tag `identifier`.

   `poll [identifier] remove` - removes the poll with the corresponding ID.

   `poll [identifier] votes` - shows current vote counts for a poll.

   `polls` - prints a list of the currently active polls

   `publish-poll [identifier]` - publishes your poll with the specified identifier

   `vote [identifier] [option-number]` - votes on a poll. Use option IDs, not the option's text



### Misc:

   `hello` - says hi back and some basic information

   `change-my-name [new name]` - changes your name to something other than your Slack display name



### Scoring and Points:

   `add-point(s) [@ user] <# points>` - gives `# points` to `@ user` if specified, 1 point by default

   `scores <@ user>` - prints a list of today's scores and running totals, for `<@ user>` if given, for everyone otherwise

   `scores-unranked` - prints a list of today's scores and running totals, sorted alphabetically instead of by ranking