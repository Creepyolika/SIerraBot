def create_list(string: str) -> list[str]:
    inp_list = string.split(',')
    final_list = []

    for song in inp_list:

        song = song.lstrip()
        song_list = song.split(" ")
        assembler = []

        for substr in song_list:

            if substr.startswith("http"):
                if assembler != []:
                    final_list.append(" ".join(assembler))
                    assembler = []
                final_list.append(substr)
            else:
                assembler.append(substr)

        if assembler != []:
            final_list.append(" ".join(assembler))
            assembler = []
    return final_list

def get_duration_string(seconds) -> str:
    hour = int(seconds/3600)
    minute = int((seconds-(hour*3600))/60)
    second = seconds-(hour*3600+minute*60)
    string = ""
    if hour:
        string += f"{hour}:"

    if minute < 10:
        string += "0"
    string += f"{minute}:"

    if second < 10:
        string += "0"
    string += f"{second}"

    return string
