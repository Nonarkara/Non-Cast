# The RSS promise

RSS is a boring miracle. A document lists episodes. Each item has a title, a date, a note, and an enclosure — usually an audio file. A directory such as Apple Podcasts or Spotify does not need a private partnership to list the show. They follow the feed. If the feed is valid, the directories can subscribe. If the feed dies, the show disappears from those directories for a mechanical reason, not a mysterious one.

That is the promise: the publisher keeps the index. Platforms may wrap it, rank it, or ignore it, but they do not own the list. A kit that “publishes” should write that list to disk as XML a human can read. Anything beyond the feed — partner APIs, dashboard tokens, private upload gates — is optional commerce, not the medium.

Enclosures should be stable URLs. Changing the path of an old episode breaks clients that already downloaded the item. New episodes get new files. The GUID of an item should not change once it has shipped. Dates should be real RFC 2822 timestamps, not slogans.

A daily show can be corpus-only. News feeds are optional beats, not the identity of the host. When a feed is slow, skip it. Eight seconds and two retries is plenty. A scraper that waits four minutes is not being thorough. It is stalling the morning.

Show notes belong in the item description. Link the sources you actually used. Do not invent a guest, a sponsor, or a statistic to look busy. The feed is a contract with the listener’s client: this file, this length, this day. Keep the contract small and keep it true.
