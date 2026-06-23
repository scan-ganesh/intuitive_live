Objective:
filter the positions based on the strategy names only

gcloud firestore fields ttls update expireAt --collection-group=candle_reference --enable-ttl

Next action item is to install TOTP based ICICIDirect's automatic login. Full conversation is available in Grok
https://grok.com/c/3c21ee6c-1014-4847-ad06-def5ba62ce82?rid=c1e142fd-b515-4489-84cb-3944e57e4e3c

Lots of secrets will also be expensive. So, keep only which are truly secrets. move the rest to env variables

We need a way to stop the trading for the day. The easiest is to disable the job and enable it the next day. Is there any better way?