require 'json'

class DirtyNode
  def initialize(file_path, profile)
    @file_path = file_path
    @profile = profile
  end

  def print_dirty_nodes()
    data = File.read(@file_path)
    json_data = JSON.load(data)
    volumes = json_data["Volumes"]
    @dirty_nodes = {}

    volumes.each do |volume|
      if check_attaching_volume(volume)
        attachment = volume["Attachments"][0]
        @dirty_nodes[attachment["InstanceId"]] = volume
      end
    end

    @dirty_nodes.each do |node, val|
      puts node
    end
  end

  def reboot_node(node)
    command = "aws ec2 reboot-instances --instance-ids #{node} --profile=#{@profile}"
    puts "Running - #{command}"
    system(command)
  end

  def check_attaching_volume(volume)
    attachments = volume["Attachments"]

    if !attachments.empty?
      attachment = attachments[0]
      attachment["State"] == "attaching"
    else
      false
    end
  end
end


a = DirtyNode.new(ARGV[0], ARGV[1])
a.print_dirty_nodes
