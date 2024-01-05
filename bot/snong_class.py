class Song:
    def __init__(
            self,
            title: str = "Unknown",
            cover_img: str = "Unknown",
            audio: str = "Unknown",
            duration_string: str = "Unknown",
            channel: str = "Unknown",
            upload: str = "Unknown",
            original_link: str = "Unknown",
        ):
        
        self.title: str = title
        self.cover_img: str = cover_img
        self.audio: str = audio
        self.duration_string: str = duration_string
        self.channel: str = channel
        self.upload: str = upload
        self.original_link: str = original_link