import reddit_stats
import reddit_stats_to_dict
import count_posts
# file has a list of subreddits and calls get_subreddit_subscribers to get subscriber count for each

subreddits = ["Georgia","tennessee","Wisconsin","Colorado","Minnesota","southcarolina","alabama","louisiana","kentucky","oregon","Oklahoma","Connecticut","utah","nevada"]

#for subreddit in subreddits:
#    print(subreddit, " ", reddit_stats_to_dict.get_subreddit_stats(subreddit))

#def count_posts_two_weeks():
for subreddit in subreddits:
	print(subreddit, "", count_posts.get_recent_post_count(subreddit))
